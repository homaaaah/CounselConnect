/**
 * ExpressionCuePanel — optional, session-long local expression cue (ADR-039).
 *
 * The Counselor starts; the Student consents once for the session. Only the
 * Student's device runs the model, and only the current rounded label/confidence
 * is shared over the call socket. Nothing is recorded, stored, or replayed.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  EXPRESSION_MIN_CONFIDENCE,
  expressionLabelIcon,
  expressionLabelText,
  expressionResultText,
} from "../../features/expression/expression";
import { scanExpression } from "../../features/expression/expressionModel";

const primaryButton = "rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50";
const LIVE_GAP_MS = 2_000;

function newRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `expr-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function pause(ms, signal) {
  return new Promise((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    const done = () => {
      clearTimeout(timer);
      signal?.removeEventListener?.("abort", done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    signal?.addEventListener?.("abort", done, { once: true });
  });
}

function CueIndicator({ result, children }) {
  const icon = expressionLabelIcon(result.label);
  return (
    <div className="flex items-center gap-3">
      {icon && (
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xl text-slate-700"
          aria-hidden="true"
        >
          <i className={`fa-regular ${icon}`}></i>
        </span>
      )}
      <p className="text-sm text-slate-800">{children}</p>
    </div>
  );
}

export default function ExpressionCuePanel({
  role,
  localStream,
  camOn,
  phase,
  expressionEvent,
  sendExpression,
  onResult,
  onActiveChange,
  scan = scanExpression,
}) {
  const isCounselor = role === "COUNSELOR";
  const isStudent = role === "STUDENT";
  const [requestId, setRequestId] = useState(null);
  const [awaitingConsent, setAwaitingConsent] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const videoRef = useRef(null);
  const abortRef = useRef(null);
  const lastEventRef = useRef(null);

  const abortScan = useCallback(() => {
    const controller = abortRef.current;
    abortRef.current = null;
    controller?.abort();
  }, []);

  const clearExchange = useCallback(() => {
    abortScan();
    onActiveChange?.(false);
    setRequestId(null);
    setAwaitingConsent(false);
    setConsentOpen(false);
    setScanning(false);
    setResult(null);
    setError("");
  }, [abortScan, onActiveChange]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    video.srcObject = localStream ?? null;
    const attempt = video.play?.();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => {
        // The scan reports an unavailable cue if the element cannot play.
      });
    }
    return () => {
      video.srcObject = null;
    };
  }, [localStream]);

  useEffect(() => {
    const event = expressionEvent;
    if (!event || lastEventRef.current === event) return;
    lastEventRef.current = event;
    if (!isStudent && !isCounselor) return;

    if (isStudent && event.event === "request") {
      abortScan();
      onActiveChange?.(false);
      setRequestId(event.id ?? null);
      setConsentOpen(Boolean(event.id));
      setAwaitingConsent(false);
      setScanning(false);
      setResult(null);
      setError("");
      setStatus("The Counselor asked to see a live expression cue for this session.");
      return;
    }
    if (event.event === "stop") {
      clearExchange();
      setStatus("The live expression cue was stopped.");
      return;
    }
    if (!isCounselor) return;
    if (!event.id || !requestId || event.id !== requestId) return;
    switch (event.event) {
      case "consent":
        setAwaitingConsent(false);
        setStatus("The Student allowed the live cue. Waiting for the first result…");
        break;
      case "decline":
        setRequestId(null);
        setAwaitingConsent(false);
        setStatus("The Student declined the live cue. The call is unaffected.");
        break;
      case "unavailable":
        setAwaitingConsent(false);
        setResult(null);
        setStatus("No cue is currently shared.");
        break;
      case "result": {
        const confidence = event.confidence;
        if (
          !expressionLabelText(event.label)
          || typeof confidence !== "number"
          || !Number.isFinite(confidence)
          || confidence < EXPRESSION_MIN_CONFIDENCE
          || confidence > 1
        ) {
          setAwaitingConsent(false);
          setResult(null);
          setStatus("No cue is currently shared.");
          break;
        }
        setAwaitingConsent(false);
        setStatus("Live cue shared by the Student.");
        setResult({ label: event.label, confidence: Math.round(confidence * 1000) / 1000 });
        break;
      }
      default:
        break;
    }
  }, [abortScan, clearExchange, expressionEvent, isCounselor, isStudent, onActiveChange, requestId]);

  useEffect(() => {
    if (phase === "connected") return;
    abortScan();
  }, [abortScan, phase]);

  useEffect(() => () => {
    abortScan();
    onActiveChange?.(false);
  }, [abortScan, onActiveChange]);

  useEffect(() => {
    if (!isStudent || !scanning || typeof document === "undefined") return undefined;
    const onVisibility = () => {
      if (document.visibilityState !== "hidden" || !abortRef.current) return;
      clearExchange();
      setStatus("The live expression cue was stopped.");
      sendExpression?.({ event: "stop" });
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [clearExchange, isStudent, scanning, sendExpression]);

  useEffect(() => {
    onResult?.(result);
  }, [onResult, result]);

  if (!isStudent && !isCounselor) return null;

  async function startSharing() {
    if (!isStudent || !requestId || scanning) return;
    const id = requestId;
    const controller = new AbortController();
    abortRef.current = controller;
    setConsentOpen(false);
    setScanning(true);
    setError("");
    setResult(null);
    setStatus("Sharing a live expression cue…");
    const consented = sendExpression?.({ event: "consent", id });
    if (consented === false) {
      onActiveChange?.(false);
      setScanning(false);
      setRequestId(null);
      setStatus("The call is unavailable. No cue was shared.");
      return;
    }
    onActiveChange?.(true);
    try {
      // ponytail: ~3s scan + 2s gap on the main thread; move to a worker if the call janks.
      while (!controller.signal.aborted) {
        const outcome = await scan(videoRef.current, { signal: controller.signal });
        if (controller.signal.aborted) break;
        if (outcome) {
          const delivered = sendExpression?.({
            event: "result",
            id,
            label: outcome.label,
            confidence: outcome.confidence,
          }) !== false;
          if (!delivered) {
            onActiveChange?.(false);
            setRequestId(null);
            setResult(null);
            setStatus("No cue was shared. The call is unaffected.");
            break;
          }
          setResult(outcome);
          setStatus("Live cue shared with the Counselor.");
        } else {
          setResult(null);
          setStatus("No cue is currently shared.");
          sendExpression?.({ event: "unavailable", id });
        }
        await pause(LIVE_GAP_MS, controller.signal);
      }
    } catch {
      if (!controller.signal.aborted) {
        onActiveChange?.(false);
        setRequestId(null);
        setResult(null);
        setStatus("");
        setError("No cue was shared. The call is unaffected.");
        sendExpression?.({ event: "unavailable", id });
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      if (!controller.signal.aborted) setScanning(false);
    }
  }

  function decline() {
    if (!requestId) return;
    sendExpression?.({ event: "decline", id: requestId });
    clearExchange();
    setStatus("You declined the live expression cue. The call is unaffected.");
  }

  function stopSharing() {
    abortScan();
    sendExpression?.({ event: "stop" });
    clearExchange();
    setStatus("The live expression cue was stopped.");
  }

  function requestCheck() {
    if (!isCounselor || requestId) return;
    const id = newRequestId();
    const delivered = sendExpression?.({ event: "request", id }) !== false;
    if (!delivered) {
      setError("The call is unavailable. Try again when the call is connected.");
      return;
    }
    setRequestId(id);
    setAwaitingConsent(true);
    setResult(null);
    setError("");
    setStatus("Waiting for the Student to allow the live cue…");
  }

  const resultText = expressionResultText(result);

  return (
    <section aria-labelledby="expression-cue-heading" className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id="expression-cue-heading" className="text-sm font-semibold text-slate-800">
            Expression cue <span className="font-normal text-slate-500">(optional)</span>
          </h3>
          <p className="mt-1 max-w-prose text-xs text-slate-500">
            Local, session-only observation. It is not a diagnosis or an assessment and never affects the call, the session, or SOS.
          </p>
        </div>
      </div>

      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        aria-hidden="true"
        tabIndex={-1}
        className="pointer-events-none absolute h-px w-px overflow-hidden opacity-0"
      />

      {isCounselor && !requestId && !result && (
        <div className="mt-3">
          <button type="button" className={primaryButton} onClick={requestCheck}>
            Start live expression cue
          </button>
        </div>
      )}

      {isCounselor && requestId && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p role="status" className="text-sm text-slate-700">
            {awaitingConsent ? "Waiting for the Student to allow the live cue…" : status}
          </p>
          <button type="button" className={secondaryButton} onClick={stopSharing}>
            Stop
          </button>
        </div>
      )}

      {isCounselor && result && (
        <div className="mt-3 space-y-2 rounded-lg border border-slate-200 bg-white p-3">
          <CueIndicator result={result}>
            Live student cue: <strong>{resultText}</strong>
          </CueIndicator>
          <p className="text-xs text-slate-500">Updates while sharing. Model confidence is not diagnostic accuracy.</p>
        </div>
      )}

      {isCounselor && !requestId && !result && status && (
        <p role="status" className="mt-3 text-sm text-slate-600">{status}</p>
      )}

      {isStudent && consentOpen && (
        <div className="mt-3 space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <p role="status" className="text-sm text-slate-800">
            The Counselor asked to see a live expression cue for this session. It runs only on this device; only the current label and confidence are shared, and nothing is saved.
          </p>
          {!camOn && (
            <p role="status" className="text-sm text-slate-700">
              Turn your camera on to allow this.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primaryButton} disabled={!camOn} onClick={() => void startSharing()}>
              Allow for this session
            </button>
            <button type="button" className={secondaryButton} onClick={decline}>
              Decline
            </button>
          </div>
        </div>
      )}

      {isStudent && scanning && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p role="status" className="text-sm text-slate-700">{status || "Sharing a live expression cue…"}</p>
          <button type="button" className={secondaryButton} onClick={stopSharing}>
            Stop sharing
          </button>
        </div>
      )}

      {isStudent && !consentOpen && !scanning && !result && status && (
        <p role="status" className="mt-3 text-sm text-slate-600">{status}</p>
      )}

      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
