/**
 * Lazy local Human expression-suggestion adapter (Phase 2, default off).
 *
 * Runs only on a caller-supplied captured frame. Frames and raw scores stay in
 * this module; callers receive only a top label or an unavailable reason.
 */

import { SUGGESTED_EXPRESSIONS, SUGGESTION_UNAVAILABLE } from "./observation";

export const SUGGESTIONS_ENABLED = import.meta.env.VITE_FACIAL_HUMAN_SUGGESTIONS === "true";

const HUMAN_EMOTION_MAP = {
  angry: "angry",
  disgust: "disgusted",
  fear: "fearful",
  happy: "happy",
  sad: "sad",
  surprise: "surprised",
  neutral: "neutral",
};

export function mapHumanEmotion(label) {
  return HUMAN_EMOTION_MAP[label] ?? null;
}

let humanPromise = null;
let humanInstance = null;

function baseUrl() {
  const base = import.meta.env.BASE_URL ?? "/";
  return base.endsWith("/") ? base : `${base}/`;
}

function abortError() {
  if (typeof DOMException === "function") {
    return new DOMException("Suggestion stopped", "AbortError");
  }
  const error = new Error("Suggestion stopped");
  error.name = "AbortError";
  return error;
}

function throwIfAborted(signal) {
  if (signal?.aborted) throw abortError();
}

function unavailable() {
  return { suggested_expression: null, unavailable_reason: SUGGESTION_UNAVAILABLE };
}

async function createHuman(backend) {
  const humanModule = await import("@vladmandic/human");
  const Human = humanModule.Human ?? humanModule.default;
  const human = new Human({
    backend,
    modelBasePath: `${baseUrl()}human/models/`,
    cacheModels: true,
    debug: false,
    face: {
      enabled: true,
      detector: { enabled: true, modelPath: "blazeface.json", maxDetected: 2 },
      mesh: { enabled: false },
      iris: { enabled: false },
      emotion: { enabled: true, modelPath: "emotion.json" },
      description: { enabled: false },
      antispoof: { enabled: false },
      liveness: { enabled: false },
    },
    body: { enabled: false },
    hand: { enabled: false },
    object: { enabled: false },
    gesture: { enabled: false },
    segmentation: { enabled: false },
  });
  await human.load();
  return human;
}

async function loadHuman() {
  if (!humanPromise) {
    humanPromise = (async () => {
      try {
        humanInstance = await createHuman("webgl");
      } catch {
        humanInstance = await createHuman("cpu");
      }
      return humanInstance;
    })().catch((error) => {
      humanPromise = null;
      humanInstance = null;
      throw error;
    });
  }
  return humanPromise;
}

export async function detectSuggestion(frame, { signal } = {}) {
  throwIfAborted(signal);
  if (!frame) return unavailable();
  const human = await loadHuman();
  throwIfAborted(signal);
  const result = await human.detect(frame);
  throwIfAborted(signal);
  const faces = result?.face ?? [];
  if (faces.length !== 1) return unavailable();
  const emotion = faces[0].emotion;
  if (!Array.isArray(emotion) || emotion.length === 0) return unavailable();
  const top = emotion.reduce((best, item) => (
    !best || (Number(item?.score) || 0) > (Number(best?.score) || 0) ? item : best
  ), null);
  const expression = mapHumanEmotion(top?.emotion);
  if (!expression || !SUGGESTED_EXPRESSIONS.includes(expression)) return unavailable();
  return { suggested_expression: expression, unavailable_reason: null };
}

export function warmSuggestionModel() {
  if (!SUGGESTIONS_ENABLED) return undefined;
  return loadHuman().catch(() => {});
}

export function disposeSuggestionModel() {
  const instance = humanInstance;
  humanInstance = null;
  humanPromise = null;
  try {
    instance?.dispose?.();
  } catch {
    // Already disposed.
  }
}
