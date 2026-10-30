/**
 * useAppointmentCall — authorized one-to-one appointment call.
 *
 * The backend relays SDP/ICE over an authenticated appointment WebSocket; media
 * is peer-to-peer and never recorded or persisted. Media is requested only when
 * the participant explicitly joins, never on mount.
 *
 * Cleanup contract: hang-up, peer departure, window close, and unmount stop
 * every local track, close the peer connection, and close the signaling socket.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../services/apiClient";
import { socketUrl } from "../../services/realtime";
import {
  isWebRtcSupported,
  mediaErrorMessage,
  parseServerEvent,
} from "./signaling";

function stopStream(stream) {
  for (const track of stream?.getTracks?.() ?? []) {
    try {
      track.stop();
    } catch {
      // Already-ended tracks are harmless.
    }
  }
}

export function useAppointmentCall({ appointmentId, canCall }) {
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState("");
  const [endReason, setEndReason] = useState("");
  const [localStream, setLocalStream] = useState(null);
  const [remoteStream, setRemoteStream] = useState(null);
  const [micOn, setMicOn] = useState(false);
  const [camOn, setCamOn] = useState(false);
  const [peerRole, setPeerRole] = useState(null);
  const [observationEvent, setObservationEvent] = useState(null);

  const mounted = useRef(false);
  const runRef = useRef(0);
  const socket = useRef(null);
  const pc = useRef(null);
  const local = useRef(null);
  const pendingCandidates = useRef([]);
  const remoteDescriptionSet = useRef(false);
  const offerStarted = useRef(false);
  const joiningRef = useRef(false);
  const iceServers = useRef([]);

  const send = useCallback((payload) => {
    const socketInstance = socket.current;
    if (!socketInstance || socketInstance.readyState !== 1) return false;
    socketInstance.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendObservation = useCallback((payload) => {
    return send({ type: "facial-observation", version: 1, ...payload });
  }, [send]);

  const cleanupCall = useCallback(() => {
    const socketInstance = socket.current;
    socket.current = null;
    if (socketInstance) {
      socketInstance.onopen = null;
      socketInstance.onmessage = null;
      socketInstance.onclose = null;
      try {
        socketInstance.close();
      } catch {
        // Already closed.
      }
    }
    const connection = pc.current;
    pc.current = null;
    if (connection) {
      connection.onicecandidate = null;
      connection.ontrack = null;
      connection.onconnectionstatechange = null;
      try {
        connection.close();
      } catch {
        // Already closed.
      }
    }
    stopStream(local.current);
    local.current = null;
    pendingCandidates.current = [];
    remoteDescriptionSet.current = false;
    offerStarted.current = false;
    joiningRef.current = false;
    if (!mounted.current) return;
    setLocalStream(null);
    setRemoteStream(null);
    setMicOn(false);
    setCamOn(false);
    setPeerRole(null);
    setObservationEvent(null);
  }, []);

  const endLocally = useCallback((reason = "") => {
    runRef.current++;
    cleanupCall();
    if (!mounted.current) return;
    setPhase("ended");
    setEndReason(reason);
  }, [cleanupCall]);

  const ensurePeer = useCallback(() => {
    if (pc.current) return pc.current;
    if (typeof RTCPeerConnection !== "function") {
      throw new Error("This browser does not support peer-to-peer calls.");
    }
    const connection = new RTCPeerConnection({ iceServers: iceServers.current });
    const stream = local.current;
    for (const track of stream?.getTracks?.() ?? []) connection.addTrack(track, stream);

    const remote = typeof MediaStream === "function" ? new MediaStream() : null;
    connection.onicecandidate = (event) => {
      if (!mounted.current || pc.current !== connection) return;
      send({
        type: "ice-candidate",
        candidate: event.candidate
          ? (event.candidate.toJSON ? event.candidate.toJSON() : event.candidate)
          : null,
      });
    };
    connection.ontrack = (event) => {
      if (!mounted.current || pc.current !== connection) return;
      const incoming = event?.streams?.[0];
      if (incoming) {
        setRemoteStream(incoming);
        return;
      }
      if (!remote || !event?.track) return;
      remote.addTrack(event.track);
      setRemoteStream(remote);
    };
    connection.onconnectionstatechange = () => {
      if (!mounted.current || pc.current !== connection) return;
      if (connection.connectionState === "connected") {
        setPhase("connected");
      } else if (connection.connectionState === "failed") {
        setPhase("failed");
        setError("The call could not connect. Try again or check your network.");
        cleanupCall();
      }
    };
    pc.current = connection;
    return connection;
  }, [cleanupCall, send]);

  const flushCandidates = useCallback(async () => {
    const connection = pc.current;
    if (!connection) return;
    while (pendingCandidates.current.length) {
      const candidate = pendingCandidates.current.shift();
      try {
        await connection.addIceCandidate(candidate);
      } catch {
        // A stale candidate must not break the call.
      }
    }
  }, []);

  const startOffer = useCallback(async () => {
    if (offerStarted.current) return;
    offerStarted.current = true;
    const run = runRef.current;
    const connection = ensurePeer();
    setPhase("negotiating");
    const offer = await connection.createOffer();
    if (run !== runRef.current || pc.current !== connection) return;
    await connection.setLocalDescription(offer);
    if (run !== runRef.current || pc.current !== connection) return;
    send({ type: "offer", sdp: connection.localDescription?.sdp ?? offer.sdp });
  }, [ensurePeer, send]);

  const handleOffer = useCallback(async (sdp) => {
    if (pc.current && remoteDescriptionSet.current) return;
    const run = runRef.current;
    const connection = ensurePeer();
    setPhase("negotiating");
    await connection.setRemoteDescription({ type: "offer", sdp });
    if (run !== runRef.current || pc.current !== connection) return;
    remoteDescriptionSet.current = true;
    await flushCandidates();
    if (run !== runRef.current || pc.current !== connection) return;
    const answer = await connection.createAnswer();
    if (run !== runRef.current || pc.current !== connection) return;
    await connection.setLocalDescription(answer);
    if (run !== runRef.current || pc.current !== connection) return;
    send({ type: "answer", sdp: connection.localDescription?.sdp ?? answer.sdp });
  }, [ensurePeer, flushCandidates, send]);

  const handleAnswer = useCallback(async (sdp) => {
    const connection = pc.current;
    if (!connection || remoteDescriptionSet.current) return;
    const run = runRef.current;
    await connection.setRemoteDescription({ type: "answer", sdp });
    if (run !== runRef.current || pc.current !== connection) return;
    remoteDescriptionSet.current = true;
    await flushCandidates();
  }, [flushCandidates]);

  const handleMessage = useCallback(async (event) => {
    const message = parseServerEvent(event.data);
    if (!message) return;
    const run = runRef.current;
    const activeSocket = socket.current;
    try {
      switch (message.type) {
        case "room-state":
          if (message.peer_role) setPeerRole(message.peer_role);
          if (message.peer_present && message.initiator) await startOffer();
          break;
        case "peer-joined":
          if (message.peer_role) setPeerRole(message.peer_role);
          break;
        case "offer":
          await handleOffer(message.sdp);
          break;
        case "answer":
          await handleAnswer(message.sdp);
          break;
        case "ice-candidate":
          if (message.candidate && remoteDescriptionSet.current && pc.current) {
            await pc.current.addIceCandidate(message.candidate);
          } else if (message.candidate) {
            pendingCandidates.current.push(message.candidate);
          }
          break;
        case "peer-left":
          endLocally(message.reason === "REPLACED" ? "REPLACED" : "PEER_LEFT");
          break;
        case "call-ended":
          endLocally(message.reason || "PEER_HUNG_UP");
          break;
        case "facial-observation":
          if (mounted.current && run === runRef.current && socket.current === activeSocket) {
            setObservationEvent(message);
          }
          break;
        default:
          break;
      }
    } catch {
      if (mounted.current && run === runRef.current && socket.current === activeSocket) {
        setPhase("failed");
        setError("The call could not connect. Try again.");
        cleanupCall();
      }
    }
  }, [cleanupCall, endLocally, handleAnswer, handleOffer, startOffer]);

  const join = useCallback(async () => {
    if (socket.current || pc.current || joiningRef.current) return;
    if (!canCall) {
      setPhase("ended");
      setEndReason("CALL_UNAVAILABLE");
      return;
    }
    joiningRef.current = true;
    const run = ++runRef.current;
    const live = () => mounted.current && run === runRef.current;
    setError("");
    setEndReason("");
    setPeerRole(null);
    setPhase("joining");
    try {
      const config = await request(`/appointments/${appointmentId}/call`);
      if (!live()) return;
      if (!config?.can_call) {
        setPhase("ended");
        setEndReason("CALL_UNAVAILABLE");
        return;
      }
      if (!isWebRtcSupported()) {
        throw new Error("This browser does not support WebRTC calls. Try a recent Chrome, Edge, Firefox, or Safari.");
      }
      iceServers.current = config.ice_servers ?? [];
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      if (!live()) {
        stopStream(stream);
        return;
      }
      local.current = stream;
      setLocalStream(stream);
      setMicOn(stream.getAudioTracks().some((track) => track.enabled));
      setCamOn(stream.getVideoTracks().some((track) => track.enabled));

      const url = socketUrl(`/appointments/${appointmentId}/call/ws`);
      if (!url || typeof WebSocket === "undefined") {
        throw new Error("Real-time signaling is unavailable. Try a different browser.");
      }
      const socketInstance = new WebSocket(url);
      socket.current = socketInstance;
      socketInstance.onopen = () => {
        if (!live() || socket.current !== socketInstance) return;
        setPhase("waiting");
        send({ type: "ready" });
      };
      socketInstance.onmessage = (event) => {
        void handleMessage(event);
      };
      socketInstance.onclose = () => {
        if (socket.current !== socketInstance) return;
        socket.current = null;
        if (!mounted.current) return;
        endLocally("");
      };
    } catch (joinError) {
      if (live()) {
        cleanupCall();
        setPhase("failed");
        setError(mediaErrorMessage(joinError));
      }
    } finally {
      joiningRef.current = false;
    }
  }, [appointmentId, canCall, cleanupCall, endLocally, handleMessage, send]);

  const hangUp = useCallback(() => {
    send({ type: "hangup" });
    runRef.current++;
    cleanupCall();
    if (!mounted.current) return;
    setPhase("ended");
    setEndReason("YOU_HUNG_UP");
    setError("");
  }, [cleanupCall, send]);

  const toggleMic = useCallback(() => {
    const tracks = local.current?.getAudioTracks?.() ?? [];
    if (!tracks.length) return;
    const next = !tracks.every((track) => track.enabled);
    for (const track of tracks) track.enabled = next;
    setMicOn(next);
  }, []);

  const toggleCam = useCallback(() => {
    const tracks = local.current?.getVideoTracks?.() ?? [];
    if (!tracks.length) return;
    const next = !tracks.every((track) => track.enabled);
    for (const track of tracks) track.enabled = next;
    setCamOn(next);
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      runRef.current++;
      cleanupCall();
    };
  }, [cleanupCall]);

  useEffect(() => {
    if (canCall) return;
    if (["joining", "waiting", "negotiating", "connected"].includes(phase)) {
      endLocally("CALL_UNAVAILABLE");
    }
  }, [canCall, endLocally, phase]);

  return {
    phase,
    error,
    endReason,
    localStream,
    remoteStream,
    micOn,
    camOn,
    peerRole,
    observationEvent,
    active: Boolean(localStream) || ["joining", "waiting", "negotiating", "connected"].includes(phase),
    join,
    hangUp,
    sendObservation,
    toggleMic,
    toggleCam,
  };
}
