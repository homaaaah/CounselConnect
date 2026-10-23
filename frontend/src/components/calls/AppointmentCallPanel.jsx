/**
 * AppointmentCallPanel — the only video-call surface.
 *
 * Shows a window message before/after the appointment call window and a
 * peer-to-peer call with explicit join, device toggles, and cleanup. It never
 * requests media on mount and never records or stores media.
 */

import { useEffect, useRef, useState } from "react";
import { formatSchedule } from "../../features/appointments";
import { callStatusText, useAppointmentCall } from "../../features/calls";

const primaryButton = "rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const dangerButton = "rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50";

function VideoTile({ videoRef, stream, label, muted, emptyText, children }) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    video.srcObject = stream ?? null;
    return () => {
      video.srcObject = null;
    };
  }, [stream, videoRef]);

  return (
    <div className="relative aspect-video overflow-hidden rounded-xl bg-slate-900">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={muted}
        aria-label={label}
        className="h-full w-full object-cover"
      />
      {!stream && (
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
}) {
  const call = useAppointmentCall({ appointmentId, canCall });
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const [playBlocked, setPlayBlocked] = useState(false);

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

  const now = serverTime ? new Date(serverTime).getTime() : Date.now();
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
    <section aria-labelledby="call-heading" className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="call-heading" className="font-semibold">Video call</h2>
        {call.phase === "connected" && (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">Live</span>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Peer-to-peer and not recorded. Your network address may be visible to the other participant.
      </p>

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
          <p role="status" className="text-sm text-slate-600">
            {callStatusText(call.phase, call.endReason)}
          </p>

          {(inCall || call.phase === "failed") && (
            <div className="grid gap-3 sm:grid-cols-2">
              <VideoTile
                videoRef={localVideoRef}
                stream={call.localStream}
                label="Your camera"
                muted
                emptyText={call.phase === "joining" ? "Starting camera and microphone…" : "Camera off"}
              />
              <VideoTile
                videoRef={remoteVideoRef}
                stream={call.remoteStream}
                label={otherLabel}
                emptyText="Waiting for the other participant's video."
              >
                {playBlocked && (
                  <button
                    type="button"
                    className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow"
                    onClick={playRemote}
                  >
                    Click to play
                  </button>
                )}
              </VideoTile>
            </div>
          )}

          {call.active && (
            <div className="flex flex-wrap gap-2">
              <button type="button" className={secondaryButton} aria-pressed={call.micOn} onClick={call.toggleMic}>
                Microphone
              </button>
              <button type="button" className={secondaryButton} aria-pressed={call.camOn} onClick={call.toggleCam}>
                Camera
              </button>
              <button type="button" className={dangerButton} onClick={call.hangUp}>
                Hang up &amp; stop camera
              </button>
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
