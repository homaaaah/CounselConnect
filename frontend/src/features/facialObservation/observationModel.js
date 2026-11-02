/**
 * Lazy local MediaPipe Face Landmarker adapter (ADR-040).
 *
 * Frames, landmarks, and blendshape vectors stay in this module. Callers receive
 * only a valid/invalid slot with bounded movement flags and a reason.
 */

import { detectMovements, missingRequiredScores } from "./observation";

const MODEL_VERSION = "mediapipe-face-landmarker-1";
let landmarkerPromise = null;
let landmarkerInstance = null;
let lastTimestamp = 0;

function baseUrl() {
  const base = import.meta.env.BASE_URL ?? "/";
  return base.endsWith("/") ? base : `${base}/`;
}

function abortError() {
  if (typeof DOMException === "function") {
    return new DOMException("Facial observation stopped", "AbortError");
  }
  const error = new Error("Facial observation stopped");
  error.name = "AbortError";
  return error;
}

function throwIfAborted(signal) {
  if (signal?.aborted) throw abortError();
}

function nextTimestamp() {
  const now = Math.max(Math.round(performance.now()), lastTimestamp + 1);
  lastTimestamp = now;
  return now;
}

async function createLandmarker(delegate) {
  const vision = await import("@mediapipe/tasks-vision");
  const fileset = await vision.FilesetResolver.forVisionTasks(`${baseUrl()}mediapipe/wasm`);
  return vision.FaceLandmarker.createFromOptions(fileset, {
    baseOptions: {
      modelAssetPath: `${baseUrl()}mediapipe/face_landmarker.task`,
      delegate,
    },
    runningMode: "VIDEO",
    numFaces: 2,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: false,
  });
}

async function loadLandmarker() {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      try {
        landmarkerInstance = await createLandmarker("GPU");
      } catch {
        landmarkerInstance = await createLandmarker("CPU");
      }
      return landmarkerInstance;
    })().catch((error) => {
      landmarkerPromise = null;
      landmarkerInstance = null;
      throw error;
    });
  }
  return landmarkerPromise;
}

function scoreMap(result) {
  const categories = result?.faceBlendshapes?.[0]?.categories ?? [];
  return Object.fromEntries(
    categories
      .filter(category => typeof category?.categoryName === "string")
      .map(category => [category.categoryName, category.score]),
  );
}

export function captureFrame(video) {
  if (typeof document === "undefined" || !video || video.readyState < 2) return null;
  if (!video.videoWidth || !video.videoHeight) return null;
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d")?.drawImage(video, 0, 0);
  return canvas;
}

export async function detectObservation(frame, { signal } = {}) {
  throwIfAborted(signal);
  if (!frame) {
    return { valid: false, movements: [], unavailable_reason: "LOW_QUALITY" };
  }
  const landmarker = await loadLandmarker();
  throwIfAborted(signal);
  const result = landmarker.detectForVideo(frame, nextTimestamp());
  throwIfAborted(signal);
  const faces = result?.faceLandmarks ?? [];
  if (faces.length === 0) {
    return { valid: false, movements: [], unavailable_reason: "NO_FACE" };
  }
  if (faces.length > 1) {
    return { valid: false, movements: [], unavailable_reason: "MULTIPLE_FACES" };
  }
  const scores = scoreMap(result);
  if (missingRequiredScores(scores)) {
    return { valid: false, movements: [], unavailable_reason: "READING_UNAVAILABLE" };
  }
  return {
    valid: true,
    movements: detectMovements(scores),
    unavailable_reason: null,
  };
}

export function disposeObservationModel() {
  const instance = landmarkerInstance;
  landmarkerInstance = null;
  landmarkerPromise = null;
  lastTimestamp = 0;
  try {
    instance?.close?.();
  } catch {
    // Already closed.
  }
}

export { MODEL_VERSION };
