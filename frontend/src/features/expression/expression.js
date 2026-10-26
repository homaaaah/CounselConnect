/**
 * Pure expression-cue helpers (ADR-025).
 *
 * Only a label and confidence ever leave the Student's browser. These helpers
 * turn local per-frame probabilities into one conservative shared cue; they
 * never use diagnostic language.
 */

export const EXPRESSION_LABELS = [
  "neutral",
  "happy",
  "sad",
  "angry",
  "fearful",
  "disgusted",
  "surprised",
];

export const EXPRESSION_MIN_CONFIDENCE = 0.6;
export const EXPRESSION_MIN_SAMPLES = 3;

const LABEL_TEXT = {
  neutral: "Neutral",
  happy: "Happy",
  sad: "Sad",
  angry: "Angry",
  fearful: "Fearful",
  disgusted: "Disgusted",
  surprised: "Surprised",
};

const LABEL_ICON = {
  neutral: "fa-face-meh",
  happy: "fa-face-smile",
  sad: "fa-face-frown",
  angry: "fa-face-angry",
  fearful: "fa-face-flushed",
  disgusted: "fa-face-grimace",
  surprised: "fa-face-surprise",
};

export function expressionLabelText(label) {
  return LABEL_TEXT[label] ?? "";
}

export function expressionLabelIcon(label) {
  return LABEL_ICON[label] ?? "";
}

export function expressionResultText(result) {
  if (!result) return "";
  const label = expressionLabelText(result.label);
  if (!label) return "";
  return `${label} (${Math.round(result.confidence * 100)}% confidence)`;
}

export function aggregateExpressions(samples) {
  if (!Array.isArray(samples)) return null;
  const totals = Object.fromEntries(EXPRESSION_LABELS.map((label) => [label, 0]));
  let counted = 0;
  for (const sample of samples) {
    if (!sample || typeof sample !== "object") continue;
    let usable = false;
    for (const label of EXPRESSION_LABELS) {
      const value = sample[label];
      if (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1) {
        totals[label] += value;
        usable = true;
      }
    }
    if (usable) counted += 1;
  }
  if (counted < EXPRESSION_MIN_SAMPLES) return null;
  let top = null;
  for (const label of EXPRESSION_LABELS) {
    const confidence = totals[label] / counted;
    if (!top || confidence > top.confidence) top = { label, confidence };
  }
  if (!top || top.confidence < EXPRESSION_MIN_CONFIDENCE) return null;
  return { label: top.label, confidence: Math.round(top.confidence * 1000) / 1000 };
}
