/**
 * FacialObservationPanel — optional, temporary visible-movement observation.
 *
 * Student device: detect locally, relay bounded slots, never see results.
 * Counselor device: temporary timeline and deterministic Sentence/Bullets summary.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MOVEMENTS,
  MOVEMENT_LABELS,
  SUGGESTED_EXPRESSIONS,
  SUGGESTION_LABELS,
  SUGGESTION_UNAVAILABLE,
  UNAVAILABLE_LABELS,
  applyObservationSlot,
  applySuggestion,
  buildFacts,
  buildReviewRows,
  buildSuggestionStats,
  buildTimeline,
  createObservationState,
  finishObservation,
  formatElapsed,
  formatPercent,
  latestCheck,
  latestSuggestion,
  renderObservationBullets,
  renderObservationSentence,
  startCollecting,
} from "../../features/facialObservation/observation";
import { captureFrame, detectObservation } from "../../features/facialObservation/observationModel";
import { SUGGESTIONS_ENABLED, detectSuggestion, warmSuggestionModel } from "../../features/facialObservation/suggestionModel";

const primaryButton = "rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50";
const quietButton = "rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100";
const SUGGESTION_MAX_LAG_TICKS = 5;

function ObservationTimeline({ timeline, truncated }) {
  return (
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
      {truncated && <p className="mt-2 text-xs text-amber-700">The visible timeline is truncated; full-cycle counts are preserved.</p>}
    </div>
  );
}

function suggestionRowText(row) {
  if (row.tie) return "No single most common suggestion";
  if (row.suggestion) return SUGGESTION_LABELS[row.suggestion];
  if (row.checks === row.missing) return "No suggestion";
  if (row.unavailable > 0) return "Suggestion unavailable";
  return "No suggestion";
}

function suggestionDetails(stats) {
  const counts = SUGGESTED_EXPRESSIONS
    .filter(expression => stats.counts[expression] > 0)
    .map(expression => `${SUGGESTION_LABELS[expression]}: ${stats.counts[expression]}`);
  return {
    counts: counts.length ? counts.join("; ") : "No expression suggestions",
    missing: stats.missing,
    unavailable: stats.unavailable,
    tied: stats.tied,
  };
}

function newRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `obs-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function FacialObservationPanel({
  role,
  localStream,
  camOn,
  phase,
  observationVersion,
  drainObservationEvents,
  sendObservation,
  onStatusChange,
  onOpen,
  detector = detectObservation,
  suggestionDetector = detectSuggestion,
  suggestionsEnabled = SUGGESTIONS_ENABLED,
  capture = captureFrame,
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
  const suggestionInFlightRef = useRef(false);

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
    suggestionInFlightRef.current = false;
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
    setTrackingStatus("Starting local observation...");
    if (suggestionsEnabled) warmSuggestionModel();

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
      const frame = capture(videoRef.current);
      if (!frame) {
        send("observation", id, {
          seq, elapsed_ms, valid: false, movements: [], unavailable_reason: "LOW_QUALITY",
        });
        setTrackingStatus("Reading unavailable.");
        return;
      }
      inFlightRef.current = true;
      try {
        const result = await detector(frame, { signal: controller.signal });
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
        if (valid && suggestionsEnabled && !suggestionInFlightRef.current) {
          suggestionInFlightRef.current = true;
          const suggestionSeq = seq;
          Promise.resolve()
            .then(() => suggestionDetector(frame, { signal: controller.signal }))
            .then((suggestion) => {
              if (controller.signal.aborted || seqRef.current - suggestionSeq > SUGGESTION_MAX_LAG_TICKS) return;
              const expression = SUGGESTED_EXPRESSIONS.includes(suggestion?.suggested_expression)
                ? suggestion.suggested_expression
                : null;
              send("suggestion", id, {
                seq: suggestionSeq,
                suggested_expression: expression,
                unavailable_reason: expression ? null : SUGGESTION_UNAVAILABLE,
              });
            })
            .catch(() => {
              if (controller.signal.aborted || seqRef.current - suggestionSeq > SUGGESTION_MAX_LAG_TICKS) return;
              send("suggestion", id, {
                seq: suggestionSeq,
                suggested_expression: null,
                unavailable_reason: SUGGESTION_UNAVAILABLE,
              });
            })
            .finally(() => {
              suggestionInFlightRef.current = false;
            });
        }
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
  }, [capture, detector, send, stopDetector, suggestionDetector, suggestionsEnabled]);

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
    const events = drainObservationEvents?.() ?? [];
    if (!events.length) return;
    const handleEvent = (event) => {
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
          onOpen?.();
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
      if (event.event === "suggestion" && event.request_id === requestIdRef.current) {
        setObservation(prev => applySuggestion(prev, event));
        setStatus("collecting");
        return;
      }
      if (event.event === "stop") {
        resetLocal("Facial observations stopped.");
        setStatus("stopped");
      }
    };
    for (const event of events) {
      if (event?.version === 1) handleEvent(event);
    }
  }, [drainObservationEvents, isCounselor, isStudent, observationVersion, onOpen, resetLocal, stopDetector]);

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

  const timeline = buildTimeline(observation.slots);
  const facts = buildFacts(observation, timeline);
  const reviewRows = buildReviewRows(observation);
  const suggestionStats = buildSuggestionStats(observation);
  const latestSuggestionValue = latestSuggestion(observation);
  const latest = latestCheck(observation);
  const currentLabel = latest
    ? (latest.valid && latest.movements.length
      ? latest.movements.map(movement => MOVEMENT_LABELS[movement]).join(", ")
      : "No tracked movement")
    : "No observations yet";
  const readingLabel = latest
    ? (latest.valid ? "Usable reading" : (UNAVAILABLE_LABELS[latest.unavailable_reason] || "Reading unavailable"))
    : "Waiting for the first check.";
  const latestSuggestionLabel = latestSuggestionValue?.status === "label"
    ? SUGGESTION_LABELS[latestSuggestionValue.expression]
    : latestSuggestionValue?.status === "unavailable"
      ? "Suggestion unavailable"
      : "No suggestion yet";
  const suggestionInfo = suggestionDetails(suggestionStats);
  const positiveSummary = MOVEMENTS.map(movement => `${MOVEMENT_LABELS[movement]}: ${facts.counts[movement]}`).join("; ");
  const eventSummary = MOVEMENTS.map(movement => `${MOVEMENT_LABELS[movement]}: ${facts.eventCounts[movement]}`).join("; ");
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
            With your permission, your device will detect selected visible facial movements during this call
            {suggestionsEnabled ? " and a separate local expression suggestion" : ""} and share observation data with your assigned Counselor. These observations and suggestions do not determine how you feel. The Counselor can view a temporary timeline and summary. No images or observation history are saved. You can decline or stop without losing access to counseling.
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
              <div data-testid="latest-check" className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-sm text-slate-800">
                  Latest check: <strong>{currentLabel}</strong>
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Reading: {readingLabel} · Usable samples: {facts.valid} of {facts.expected} ({formatPercent(facts.coverage)}% coverage).
                </p>
                {suggestionsEnabled && (
                  <p className="mt-1 text-xs text-slate-600">
                    Suggested expression: <strong>{latestSuggestionLabel}</strong>
                  </p>
                )}
              </div>
              <ObservationTimeline timeline={timeline} truncated={observation.truncated} />
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
              {suggestionsEnabled && (
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-sm font-medium text-slate-800">Suggested expressions (estimates)</p>
                  {reviewRows.length ? (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-left text-xs text-slate-600">
                        <thead>
                          <tr>
                            <th className="pr-3 font-medium">Time</th>
                            <th className="pr-3 font-medium">Movements detected</th>
                            <th className="font-medium">Suggested expression</th>
                          </tr>
                        </thead>
                        <tbody>
                          {reviewRows.slice(-12).map((row, index) => (
                            <tr key={`${row.startMs}-${row.endMs}-${index}`}>
                              <td className="pr-3 align-top">{formatElapsed(row.startMs)}–{formatElapsed(row.endMs)}</td>
                              <td className="pr-3 align-top">{row.movements.map(movement => MOVEMENT_LABELS[movement]).join(", ")}</td>
                              <td className="align-top">{suggestionRowText(row)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-500">No movement intervals to review.</p>
                  )}
                  <details className="mt-3 text-xs text-slate-600">
                    <summary className="cursor-pointer font-medium text-slate-700">View details</summary>
                    <p className="mt-2">Suggestions: {suggestionInfo.counts}</p>
                    <p>Missing checks: {suggestionInfo.missing} · Unavailable checks: {suggestionInfo.unavailable}</p>
                    {suggestionInfo.tied && <p>No single most common suggestion.</p>}
                  </details>
                  <p className="mt-2 text-xs text-slate-500">
                    These are estimates based on facial appearance. They do not tell us how the student felt.
                  </p>
                </div>
              )}
              <ObservationTimeline timeline={timeline} truncated={observation.truncated} />
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-sm font-medium text-slate-800">Details</p>
                <p className="mt-1 text-xs text-slate-600">Positive checks: {positiveSummary}</p>
                <p className="mt-1 text-xs text-slate-600">Sustained events: {eventSummary}</p>
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
