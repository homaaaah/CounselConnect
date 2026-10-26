/**
 * AppointmentCallPanel — the only video-call surface.
 *
 * Shows a window message before/after the appointment call window and a
 * peer-to-peer call with explicit join, device toggles, and cleanup. It never
 * requests media on mount and never records or stores media.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { formatSchedule } from "../../features/appointments";
import { callStatusText, useAppointmentCall } from "../../features/calls";
import { expressionLabelIcon, expressionResultText } from "../../features/expression/expression";
import ExpressionCuePanel from "./ExpressionCuePanel";

const primaryButton = "rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50";
const controlButton = "flex h-12 w-12 items-center justify-center rounded-full border border-white/20 bg-slate-800/80 text-lg text-white backdrop-blur transition-colors hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-white";
const endCallButton = "flex h-12 w-12 items-center justify-center rounded-full bg-red-600 text-lg text-white transition-colors hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-white";

function VideoTile({ videoRef, stream, label, muted, emptyText, className = "", children }) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    video.srcObject = stream ?? null;
    return () => {
      video.srcObject = null;
    };
  }, [stream, videoRef]);

  return (
    <div className={`relative overflow-hidden bg-slate-900 ${className}`}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={muted}
        aria-label={label}
        className="h-full w-full object-cover"
      />
      {!stream && emptyText && (
        <p className="absolute inset-0 flex items-center justify-center p-3 text-center text-sm text-slate-300">
          {emptyText}
        </p>
      )}
      {children}
    </div>
  );
}

export default function AppointmentCallPanel({
  appointmentId,
  canCall,
  startsAt,
  safetyDeadlineAt,
  serverTime,
  appointmentMode = "ONLINE",
  status = "CONFIRMED",
  now: nowProp,
  selfName,
  role,
  expressionScan,
}) {
  const call = useAppointmentCall({ appointmentId, canCall });
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const [playBlocked, setPlayBlocked] = useState(false);
  const [expressionOpen, setExpressionOpen] = useState(false);
  const [expressionLive, setExpressionLive] = useState(false);
  const [expressionCue, setExpressionCue] = useState(null);
  const expressionPopoverRef = useRef(null);
  const expressionButtonRef = useRef(null);
  const expressionWasOpenRef = useRef(false);
  const handleExpressionResult = useCallback(next => setExpressionCue(next), []);
  const handleExpressionActive = useCallback(active => {
    setExpressionLive(active);
    if (active) setExpressionOpen(false);
  }, []);

  useEffect(() => {
    const video = remoteVideoRef.current;
    if (!video || !call.remoteStream) {
      setPlayBlocked(false);
      return undefined;
    }
    let cancelled = false;
    setPlayBlocked(false);
    const attempt = video.play?.();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => {
        if (!cancelled) setPlayBlocked(true);
      });
    }
    return () => {
      cancelled = true;
    };
  }, [call.remoteStream]);

  useEffect(() => {
    const event = call.expressionEvent;
    if (!event) return;
    if (role === "STUDENT" && event.event === "request") setExpressionOpen(true);
    if (role === "COUNSELOR") {
      if (event.event === "consent") handleExpressionActive(true);
      else if (event.event === "decline" || event.event === "stop") setExpressionLive(false);
    }
  }, [call.expressionEvent, handleExpressionActive, role]);

  useEffect(() => {
    if (call.phase !== "connected") {
      setExpressionOpen(false);
      setExpressionLive(false);
      setExpressionCue(null);
    }
  }, [call.phase]);

  useEffect(() => {
    const node = expressionPopoverRef.current;
    if (node) node.inert = !expressionOpen;
    if (expressionOpen && !expressionWasOpenRef.current) node?.focus?.();
    if (!expressionOpen && expressionWasOpenRef.current) expressionButtonRef.current?.focus?.();
    expressionWasOpenRef.current = expressionOpen;
  }, [call.phase, expressionOpen, role]);

  useEffect(() => {
    if (!expressionOpen || typeof document === "undefined") return undefined;
    const onKeyDown = event => {
      if (event.key === "Escape") setExpressionOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [expressionOpen]);

  const now = Number.isFinite(nowProp)
    ? nowProp
    : serverTime
      ? new Date(serverTime).getTime()
      : Date.now();
  const startTime = new Date(startsAt).getTime();
  const deadline = new Date(safetyDeadlineAt).getTime();
  const callableAppointment = appointmentMode === "ONLINE" && status === "CONFIRMED";
  const beforeWindow = callableAppointment && Number.isFinite(startTime) && now < startTime;
  const afterWindow = callableAppointment && Number.isFinite(deadline) && now >= deadline;
  const inCall = call.active || ["connected", "negotiating"].includes(call.phase);
  const otherLabel = call.peerRole === "COUNSELOR" ? "Counselor" : call.peerRole === "STUDENT" ? "Student" : "Other participant";

  async function playRemote() {
    try {
      await remoteVideoRef.current?.play();
      setPlayBlocked(false);
    } catch {
      // Keep the control visible.
    }
  }

  return (
    <section aria-labelledby="call-heading" className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
      <h2 id="call-heading" className="sr-only">Video call</h2>

      {!canCall && (
        <p role="status" className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          {!callableAppointment
            ? "Video call is unavailable for this appointment."
            : beforeWindow
              ? `Video call opens at ${formatSchedule(startsAt)}.`
              : afterWindow
                ? "The video call window has ended."
                : "Video call is unavailable for this appointment."}
        </p>
      )}

      {canCall && call.phase === "idle" && (
        <div className="mt-3 space-y-2">
          <button type="button" className={primaryButton} onClick={() => void call.join()}>
            Join video call
          </button>
          <p className="text-xs text-slate-500">The other participant must also join from their scheduled session page.</p>
        </div>
      )}

      {canCall && call.phase !== "idle" && (
        <div className="mt-3 space-y-3">
          {call.error && (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {call.error}
            </p>
          )}
          <p role="status" className="sr-only">
            {callStatusText(call.phase, call.endReason)}
          </p>

          {(inCall || call.phase === "failed") && (
            <div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-slate-900">
              <VideoTile
                videoRef={remoteVideoRef}
                stream={call.remoteStream}
                label={otherLabel}
                emptyText="Waiting for the other participant's video."
                className="h-full w-full"
              >
                {playBlocked && (
                  <button
                    type="button"
                    className="absolute inset-0 flex items-center justify-center bg-black/40"
                    onClick={playRemote}
                  >
                    <span className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow">Click to play</span>
                  </button>
                )}

                {call.localStream && (
                  <div className="absolute right-3 top-3 w-32 overflow-hidden rounded-lg ring-2 ring-white/40 sm:w-40">
                    <VideoTile
                      videoRef={localVideoRef}
                      stream={call.localStream}
                      label="Your camera"
                      muted
                      className="aspect-video w-full"
                    >
                      <span className="absolute inset-x-0 bottom-0 bg-black/50 px-2 py-0.5 text-[10px] font-medium text-white">
                        {selfName || "You"}
                      </span>
                    </VideoTile>
                  </div>
                )}

                {role === "COUNSELOR" && call.phase === "connected" && expressionCue && (
                  <div
                    data-testid="expression-cue-badge"
                    className="absolute left-3 top-3 z-10 flex max-w-[calc(100%-9rem)] items-start gap-2 rounded-lg bg-black/70 px-3 py-2 text-xs text-white shadow-lg backdrop-blur"
                  >
                    <i className={`fa-regular ${expressionLabelIcon(expressionCue.label)} mt-0.5`} aria-hidden="true"></i>
                    <span>
                      Live student cue: <strong>{expressionResultText(expressionCue)}</strong>
                    </span>
                  </div>
                )}

                {call.active && (
                  <div className="absolute inset-x-0 bottom-4 flex justify-center gap-3">
                    <button
                      type="button"
                      className={controlButton}
                      aria-label="Microphone"
                      aria-pressed={call.micOn}
                      title={call.micOn ? "Mute microphone" : "Unmute microphone"}
                      onClick={call.toggleMic}
                    >
                      <i className={call.micOn ? "fa-solid fa-microphone" : "fa-solid fa-microphone-slash"} aria-hidden="true"></i>
                    </button>
                    <button
                      type="button"
                      className={controlButton}
                      aria-label="Camera"
                      aria-pressed={call.camOn}
                      title={call.camOn ? "Turn camera off" : "Turn camera on"}
                      onClick={call.toggleCam}
                    >
                      <i className={call.camOn ? "fa-solid fa-video" : "fa-solid fa-video-slash"} aria-hidden="true"></i>
                    </button>
                    {call.phase === "connected" && ["STUDENT", "COUNSELOR"].includes(role) && (
                      <button
                        ref={expressionButtonRef}
                        type="button"
                        className={`${controlButton} ${expressionLive ? "ring-2 ring-emerald-400" : expressionOpen ? "ring-2 ring-white/60" : ""}`}
                        aria-label="Expression cue"
                        aria-expanded={expressionOpen}
                        aria-controls="expression-cue-popover"
                        title={expressionLive ? "Expression cue is live" : expressionOpen ? "Hide expression cue" : "Show expression cue"}
                        onClick={() => setExpressionOpen(open => !open)}
                      >
                        <i className="fa-regular fa-face-smile" aria-hidden="true"></i>
                      </button>
                    )}
                    <button
                      type="button"
                      className={endCallButton}
                      aria-label="End call"
                      title="Hang up and stop camera"
                      onClick={call.hangUp}
                    >
                      <i className="fa-solid fa-phone-slash" aria-hidden="true"></i>
                    </button>
                  </div>
                )}

                {call.phase === "connected" && ["STUDENT", "COUNSELOR"].includes(role) && (
                  <div
                    ref={expressionPopoverRef}
                    id="expression-cue-popover"
                    role="dialog"
                    tabIndex={-1}
                    aria-labelledby="expression-cue-heading"
                    aria-hidden={!expressionOpen}
                    onKeyDown={event => {
                      if (event.key === "Escape") setExpressionOpen(false);
                    }}
                    className={`absolute bottom-20 left-3 z-10 w-[min(22rem,calc(100%-1.5rem))] max-h-[calc(100%-6rem)] overflow-y-auto rounded-xl shadow-xl transition-opacity ${expressionOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
                  >
                    <div className="relative">
                      <button
                        type="button"
                        className="absolute right-2 top-2 z-10 rounded-full bg-white/90 p-1.5 text-slate-600 shadow hover:bg-white"
                        aria-label="Close expression cue"
                        onClick={() => setExpressionOpen(false)}
                      >
                        <i className="fa-solid fa-xmark" aria-hidden="true"></i>
                      </button>
                      <ExpressionCuePanel
                        role={role}
                        localStream={call.localStream}
                        camOn={call.camOn}
                        phase={call.phase}
                        expressionEvent={call.expressionEvent}
                        sendExpression={call.sendExpression}
                        onResult={role === "COUNSELOR" ? handleExpressionResult : undefined}
                        onActiveChange={handleExpressionActive}
                        scan={expressionScan}
                      />
                    </div>
                  </div>
                )}
              </VideoTile>
            </div>
          )}

          {call.phase === "failed" && !call.active && (
            <button type="button" className={primaryButton} onClick={() => void call.join()}>
              Try again
            </button>
          )}

          {call.phase === "ended" && canCall && (
            <button type="button" className={primaryButton} onClick={() => void call.join()}>
              Rejoin call
            </button>
          )}
        </div>
      )}
    </section>
  );
}
