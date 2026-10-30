/**
 * FacialObservationPanel — optional, temporary visible-movement observation.
 *
 * Student device: detect locally, relay bounded slots, never see results.
 * Counselor device: temporary timeline and deterministic Sentence/Bullets summary.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MOVEMENT_LABELS,
  UNAVAILABLE_LABELS,
  applyObservationSlot,
  buildFacts,
  buildTimeline,
  createObservationState,
  finishObservation,
  formatElapsed,
  formatPercent,
  renderObservationBullets,
  renderObservationSentence,
  startCollecting,
} from "../../features/facialObservation/observation";
import { detectObservation } from "../../features/facialObservation/observationModel";

const primaryButton = "rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50";
const quietButton = "rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100";

function newRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `obs-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function latestMovements(state) {
  for (let index = state.slots.length - 1; index >= 0; index -= 1) {
    const slot = state.slots[index];
    if (slot.valid) return slot.movements;
  }
  return [];
}

export default function FacialObservationPanel({
  role,
  localStream,
  camOn,
  phase,
  observationEvent,
  sendObservation,
  onStatusChange,
  detector = detectObservation,
}) {
  const isCounselor = role === "COUNSELOR";
  const isStudent = role === "STUDENT";
  const [requestId, setRequestId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [consentOpen, setConsentOpen] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");
  const [observation, setObservation] = useState(() => createObservationState());
  const [summaryStyle, setSummaryStyle] = useState("sentence");
  const [trackingStatus, setTrackingStatus] = useState("");
  const videoRef = useRef(null);
  const abortRef = useRef(null);
  const timerRef = useRef(null);
  const seqRef = useRef(0);
  const startedAtRef = useRef(0);
  const inFlightRef = useRef(false);
  const requestIdRef = useRef(null);
  const camOnRef = useRef(camOn);
  const lastEventRef = useRef(null);

  useEffect(() => {
    camOnRef.current = camOn;
  }, [camOn]);

  const stopDetector = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const controller = abortRef.current;
    abortRef.current = null;
    controller?.abort();
    inFlightRef.current = false;
  }, []);

  const resetLocal = useCallback((message = "") => {
    stopDetector();
    setRequestId(null);
    requestIdRef.current = null;
    setConsentOpen(false);
    setStatus("idle");
    setStatusText(message);
    setError("");
    setTrackingStatus("");
    setObservation(createObservationState());
  }, [stopDetector]);

  const send = useCallback((event, id = requestIdRef.current, extra = {}) => {
    if (!id) return false;
    return sendObservation?.({ event, request_id: id, ...extra }) !== false;
  }, [sendObservation]);

  const startDetector = useCallback((id) => {
    stopDetector();
    const controller = new AbortController();
    abortRef.current = controller;
    seqRef.current = 0;
    startedAtRef.current = Date.now();
    setStatus("collecting");
    setStatusText("Sharing facial observations.");
    setTrackingStatus("Starting local observation…");

    const tick = async () => {
      if (controller.signal.aborted) return;
      const seq = seqRef.current;
      seqRef.current += 1;
      const elapsed_ms = Math.max(0, Date.now() - startedAtRef.current);
      if (inFlightRef.current) {
        send("observation", id, {
          seq, elapsed_ms, valid: false, movements: [], unavailable_reason: "BUSY",
        });
        return;
      }
      if (!camOnRef.current) {
        send("observation", id, {
          seq, elapsed_ms, valid: false, movements: [], unavailable_reason: "CAMERA_OFF",
        });
        setTrackingStatus("Camera off.");
        return;
      }
      inFlightRef.current = true;
      try {
        const result = await detector(videoRef.current, { signal: controller.signal });
        if (controller.signal.aborted) return;
        const valid = Boolean(result?.valid);
        const movements = valid ? (result?.movements ?? []) : [];
        const slot = {
          request_id: id,
          seq,
          elapsed_ms,
          valid,
          movements,
          unavailable_reason: valid ? null : (result?.unavailable_reason ?? "MODEL_ERROR"),
        };
        if (!send("observation", id, slot)) {
          setStatusText("The call is unavailable. No observation was shared.");
          setStatus("stopped");
          stopDetector();
          return;
        }
        setTrackingStatus(valid
          ? "Local observation active."
          : (UNAVAILABLE_LABELS[slot.unavailable_reason] || "Unable to observe."));
      } catch {
        if (!controller.signal.aborted) {
          send("observation", id, {
            seq, elapsed_ms, valid: false, movements: [], unavailable_reason: "MODEL_ERROR",
          });
          send("stop", id);
          stopDetector();
          setRequestId(null);
          requestIdRef.current = null;
          setStatus("stopped");
          setStatusText("");
          setError("Facial observation stopped. The call is unaffected.");
        }
      } finally {
        inFlightRef.current = false;
      }
    };

    timerRef.current = setInterval(tick, 1000);
    void tick();
  }, [detector, send, stopDetector]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    video.srcObject = localStream ?? null;
    const attempt = video.play?.();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => {});
    }
    return () => {
      video.srcObject = null;
    };
  }, [localStream]);

  useEffect(() => {
    const event = observationEvent;
    if (!event || lastEventRef.current === event || event.version !== 1) return;
    lastEventRef.current = event;

    if (isStudent) {
      if (event.event === "request") {
        stopDetector();
        setRequestId(event.request_id);
        requestIdRef.current = event.request_id;
        setConsentOpen(true);
        setStatus("requested");
        setStatusText("The Counselor requested facial observations.");
        setTrackingStatus("");
        setError("");
        return;
      }
      if (event.event === "finish" && event.request_id === requestIdRef.current) {
        stopDetector();
        setRequestId(null);
        requestIdRef.current = null;
        setConsentOpen(false);
        setStatus("finished");
        setStatusText("The Counselor finished the observations.");
        setTrackingStatus("");
        return;
      }
      if (event.event === "stop") {
        resetLocal("Facial observations stopped.");
        setStatus("stopped");
      }
      return;
    }

    if (!isCounselor) return;
    if (event.event === "consent" && event.request_id === requestIdRef.current) {
      setStatus("collecting");
      setObservation(prev => startCollecting(prev));
      setStatusText("The Student allowed facial observations.");
      return;
    }
    if (event.event === "decline" && event.request_id === requestIdRef.current) {
      setRequestId(null);
      requestIdRef.current = null;
      setObservation(createObservationState());
      setStatus("declined");
      setStatusText("The Student declined facial observations. The call is unaffected.");
      return;
    }
    if (event.event === "observation" && event.request_id === requestIdRef.current) {
      setObservation(prev => applyObservationSlot(prev, event));
      setStatus("collecting");
      return;
    }
    if (event.event === "stop") {
      resetLocal("Facial observations stopped.");
      setStatus("stopped");
    }
  }, [isCounselor, isStudent, observationEvent, resetLocal, stopDetector]);

  useEffect(() => {
    if (phase === "connected") return;
    resetLocal();
  }, [phase, resetLocal]);

  useEffect(() => () => {
    stopDetector();
  }, [stopDetector]);

  useEffect(() => {
    if (!isStudent || status !== "collecting" || typeof document === "undefined") return undefined;
    const onVisibility = () => {
      if (document.visibilityState !== "hidden") return;
      const id = requestIdRef.current;
      stopDetector();
      if (id) sendObservation?.({ event: "stop", request_id: id });
      resetLocal("Observations stopped when the tab was hidden.");
      setStatus("stopped");
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      if (typeof document !== "undefined") document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [isStudent, resetLocal, sendObservation, status, stopDetector]);

  useEffect(() => {
    onStatusChange?.({
      active: status === "collecting",
      reviewing: status === "reviewing",
    });
  }, [onStatusChange, status]);

  useEffect(() => {
    if (status !== "reviewing" || !observation.expiresAt) return undefined;
    const remaining = Math.max(0, observation.expiresAt - Date.now());
    const timer = setTimeout(() => {
      resetLocal("The temporary observation review expired.");
      setStatus("expired");
    }, remaining);
    return () => clearTimeout(timer);
  }, [observation.expiresAt, resetLocal, status]);

  if (!isStudent && !isCounselor) return null;

  function requestObservations() {
    if (!isCounselor || requestId) return;
    const id = newRequestId();
    if (sendObservation?.({ event: "request", request_id: id }) === false) {
      setError("The call is unavailable. Try again when the call is connected.");
      return;
    }
    setRequestId(id);
    requestIdRef.current = id;
    setObservation(createObservationState(id, "requested"));
    setStatus("requested");
    setStatusText("Waiting for the Student to allow facial observations.");
    setSummaryStyle("sentence");
    setError("");
  }

  function allowObservations() {
    if (!isStudent || !requestId || status === "collecting") return;
    if (send("consent")) {
      setConsentOpen(false);
      startDetector(requestId);
    } else {
      setError("The call is unavailable. No observation was shared.");
    }
  }

  function declineObservations() {
    if (!isStudent || !requestId) return;
    send("decline");
    resetLocal("You declined facial observations. The call is unaffected.");
    setStatus("declined");
  }

  function stopSharing() {
    if (isStudent) {
      const id = requestIdRef.current;
      stopDetector();
      if (id) send("stop", id);
      resetLocal("Facial observations stopped.");
      setStatus("stopped");
      return;
    }
    if (requestId) send("stop");
    stopDetector();
    resetLocal("Facial observations stopped.");
    setStatus("stopped");
  }

  function finishObservations() {
    if (!isCounselor || status !== "collecting" || !requestId) return;
    if (!send("finish")) {
      setError("The call is unavailable. The observation remains active.");
      return;
    }
    setObservation(prev => finishObservation(prev));
    setStatus("reviewing");
    setStatusText("Observations finished. Review is temporary.");
  }

  function clearReview() {
    resetLocal("The temporary observation review was cleared.");
    setStatus("idle");
  }

  const facts = buildFacts(observation);
  const timeline = buildTimeline(observation.slots);
  const current = latestMovements(observation);
  const expiresLabel = observation.expiresAt
    ? new Date(observation.expiresAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <section aria-labelledby="facial-observation-heading" className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <h3 id="facial-observation-heading" className="text-sm font-semibold text-slate-800">
        Facial observation <span className="font-normal text-slate-500">(optional)</span>
      </h3>
      <p className="mt-1 max-w-prose text-xs text-slate-500">
        Optional, local, session-only observation. Visible movements do not establish emotion, diagnosis, or assessment and never affect the call, session, or SOS.
      </p>

      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        aria-hidden="true"
        tabIndex={-1}
        className="pointer-events-none absolute h-px w-px overflow-hidden opacity-0"
      />

      {isStudent && consentOpen && (
        <div className="mt-3 space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <p role="status" className="text-sm text-slate-800">
            With your permission, your device will detect selected visible facial movements during this call and share observation data with your assigned Counselor. These observations do not determine how you feel. The Counselor can view a temporary timeline and summary. No images or observation history are saved. You can decline or stop without losing access to counseling.
          </p>
          {!camOn && <p role="status" className="text-sm text-slate-700">Turn your camera on to allow this.</p>}
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primaryButton} disabled={!camOn} onClick={allowObservations}>
              Allow for this session
            </button>
            <button type="button" className={secondaryButton} onClick={declineObservations}>
              Decline
            </button>
          </div>
        </div>
      )}

      {isStudent && status === "collecting" && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <p role="status" className="text-sm text-slate-700">{statusText || "Sharing facial observations."}</p>
            <button type="button" className={secondaryButton} onClick={stopSharing}>
              Stop sharing
            </button>
          </div>
          {trackingStatus && <p className="text-sm text-slate-600">{trackingStatus}</p>}
        </div>
      )}

      {isStudent && ["finished", "stopped", "declined", "idle", "expired"].includes(status) && statusText && (
        <p role="status" className="mt-3 text-sm text-slate-600">{statusText}</p>
      )}

      {isCounselor && (
        <div className="mt-3 space-y-3">
          {statusText && <p role="status" className="text-sm text-slate-700">{statusText}</p>}

          {!requestId && ["idle", "declined", "stopped", "expired"].includes(status) && (
            <button type="button" className={primaryButton} onClick={requestObservations}>
              Request facial observations
            </button>
          )}

          {status === "requested" && (
            <button type="button" className={secondaryButton} onClick={stopSharing}>Stop</button>
          )}

          {status === "collecting" && (
            <>
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-sm text-slate-800">
                  Current supported movement: <strong>{current.length ? current.map(movement => MOVEMENT_LABELS[movement]).join(", ") : "None in the latest usable sample"}</strong>
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Usable samples: {facts.valid} of {facts.expected} ({formatPercent(facts.coverage)}% coverage).
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-sm font-medium text-slate-800">Temporary timeline</p>
                {timeline.length ? (
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    {timeline.slice(-8).map((event, index) => (
                      <li key={`${event.movement}-${event.startMs}-${index}`}>
                        {formatElapsed(event.startMs)}–{formatElapsed(event.endMs)} · {MOVEMENT_LABELS[event.movement]}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">No supported movement events yet.</p>
                )}
                {observation.truncated && <p className="mt-2 text-xs text-amber-700">The visible timeline is truncated; full-cycle counts are preserved.</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={primaryButton} onClick={finishObservations}>
                  Finish observations and review
                </button>
                <button type="button" className={secondaryButton} onClick={stopSharing}>Stop</button>
              </div>
            </>
          )}

          {status === "reviewing" && (
            <>
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <h4 className="text-sm font-semibold text-slate-800">Facial observation summary</h4>
                <p className="mt-1 text-xs text-amber-700">
                  Temporary — clears by {expiresLabel} or when you leave/end this session.
                </p>
                <fieldset className="mt-3">
                  <legend className="text-xs font-medium text-slate-600">Summary style</legend>
                  <div className="mt-1 flex gap-4 text-sm text-slate-700">
                    <label className="flex items-center gap-1">
                      <input type="radio" name="observation-summary-style" value="sentence" checked={summaryStyle === "sentence"} onChange={() => setSummaryStyle("sentence")} />
                      Sentence
                    </label>
                    <label className="flex items-center gap-1">
                      <input type="radio" name="observation-summary-style" value="bullets" checked={summaryStyle === "bullets"} onChange={() => setSummaryStyle("bullets")} />
                      Bullets
                    </label>
                  </div>
                </fieldset>
                <div className="mt-3 text-sm text-slate-700">
                  {summaryStyle === "sentence" ? (
                    <p>{renderObservationSentence(facts)}</p>
                  ) : (
                    <ul className="list-disc space-y-1 pl-5">
                      {renderObservationBullets(facts).map((line, index) => <li key={index}>{line}</li>)}
                    </ul>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={quietButton} onClick={clearReview}>Clear review</button>
              </div>
            </>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}
    </section>
  );
}
