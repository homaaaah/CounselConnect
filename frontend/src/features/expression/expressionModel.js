/**
 * Lazy, on-device expression model (ADR-025).
 *
 * The model package and weights are loaded only after the Student allows a
 * check. Frames are read from the local call video element and never leave the
 * browser; only the aggregated label/confidence is returned to the caller.
 */

import { EXPRESSION_LABELS, aggregateExpressions } from "./expression";

const FRAME_COUNT = 10;
const FRAME_INTERVAL_MS = 300;
const SCAN_TIMEOUT_MS = 15_000;
const VIDEO_READY_TIMEOUT_MS = 3_000;

let modelsPromise = null;

function modelBaseUrl() {
  const base = import.meta.env.BASE_URL ?? "/";
  return `${base.endsWith("/") ? base : `${base}/`}models`;
}

function abortError() {
  if (typeof DOMException === "function") {
    return new DOMException("Expression check cancelled", "AbortError");
  }
  const error = new Error("Expression check cancelled");
  error.name = "AbortError";
  return error;
}

function throwIfAborted(signal) {
  if (signal?.aborted) throw abortError();
}

function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener?.("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(abortError());
    }
    signal?.addEventListener?.("abort", onAbort, { once: true });
  });
}

async function loadModels() {
  if (!modelsPromise) {
    modelsPromise = (async () => {
      const faceapi = await import("@vladmandic/face-api");
      const uri = modelBaseUrl();
      await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(uri),
        faceapi.nets.faceExpressionNet.loadFromUri(uri),
      ]);
      return faceapi;
    })().catch((error) => {
      modelsPromise = null;
      throw error;
    });
  }
  return modelsPromise;
}

async function waitForFrame(video, signal) {
  if (!video || typeof video.readyState !== "number") {
    throw new Error("No camera frame is available.");
  }
  if (video.readyState >= 2) return;
  if (typeof video.addEventListener !== "function") {
    throw new Error("The camera is not ready.");
  }
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("The camera is not ready."));
    }, VIDEO_READY_TIMEOUT_MS);
    const onReady = () => {
      if (video.readyState >= 2) {
        cleanup();
        resolve();
      }
    };
    const onAbort = () => {
      cleanup();
      reject(abortError());
    };
    function cleanup() {
      clearTimeout(timer);
      video.removeEventListener?.("loadeddata", onReady);
      video.removeEventListener?.("playing", onReady);
      signal?.removeEventListener?.("abort", onAbort);
    }
    video.addEventListener("loadeddata", onReady);
    video.addEventListener("playing", onReady);
    signal?.addEventListener?.("abort", onAbort, { once: true });
  });
}

function sampleFromDetection(detection) {
  const expressions = detection?.expressions;
  if (!expressions) return null;
  const sample = {};
  let usable = false;
  for (const label of EXPRESSION_LABELS) {
    const value = expressions[label];
    if (typeof value === "number" && Number.isFinite(value)) {
      sample[label] = value;
      usable = true;
    }
  }
  return usable ? sample : null;
}

export async function scanExpression(video, { signal } = {}) {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener?.("abort", forwardAbort, { once: true });

  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      const error = new Error("The expression check timed out.");
      error.name = "TimeoutError";
      reject(error);
    }, SCAN_TIMEOUT_MS);
  });

  const run = async () => {
    throwIfAborted(controller.signal);
    const faceapi = await loadModels();
    throwIfAborted(controller.signal);
    await waitForFrame(video, controller.signal);
    const options = new faceapi.TinyFaceDetectorOptions({
      inputSize: 224,
      scoreThreshold: 0.5,
    });
    const samples = [];
    for (let index = 0; index < FRAME_COUNT; index += 1) {
      if (index > 0) await delay(FRAME_INTERVAL_MS, controller.signal);
      throwIfAborted(controller.signal);
      const detection = await faceapi
        .detectSingleFace(video, options)
        .withFaceExpressions();
      const sample = sampleFromDetection(detection);
      if (sample) samples.push(sample);
    }
    return aggregateExpressions(samples);
  };

  try {
    return await Promise.race([run(), timeout]);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener?.("abort", forwardAbort);
  }
}
