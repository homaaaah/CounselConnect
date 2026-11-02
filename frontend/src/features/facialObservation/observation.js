/**
 * Pure facial-observation rules (ADR-040/ADR-041).
 *
 * Only bounded movement/quality slots and local top-label suggestions are
 * handled here. No frames, landmarks, embeddings, or clinical conclusions.
 */

export const OBSERVATION_VERSION = 1;
export const DETECTOR_VERSION = "mediapipe-face-landmarker-1";
export const REVIEW_WINDOW_MS = 5 * 60 * 1000;
export const RING_SIZE = 7_200;
export const SUFFICIENCY_MIN_VALID = 30;
export const SUFFICIENCY_MIN_COVERAGE = 50;
export const ELAPSED_EVENT_GAP_MS = 2_000;

export const MOVEMENTS = ["smile", "brow_raise", "brow_furrow", "lip_corners_lowered"];
export const ENABLED_MOVEMENTS = ["smile", "brow_raise", "brow_furrow", "lip_corners_lowered"];
export const MOVEMENT_LABELS = {
  smile: "Smile",
  brow_raise: "Brows raised",
  brow_furrow: "Brows lowered",
  lip_corners_lowered: "Lip corners lowered",
};
export const MOVEMENT_ICONS = {
  smile: "fa-face-smile",
  brow_raise: "fa-face-surprise",
  brow_furrow: "fa-face-frown",
  lip_corners_lowered: "fa-face-sad-tear",
};
export const MOVEMENT_REQUIRED_SCORES = {
  smile: ["mouthSmileLeft", "mouthSmileRight"],
  brow_raise: ["browInnerUp"],
  brow_furrow: ["browDownLeft", "browDownRight"],
  lip_corners_lowered: ["mouthFrownLeft", "mouthFrownRight"],
};
export const SUGGESTED_EXPRESSIONS = [
  "neutral",
  "happy",
  "sad",
  "angry",
  "fearful",
  "disgusted",
  "surprised",
];
export const SUGGESTION_LABELS = {
  neutral: "Neutral",
  happy: "Happy",
  sad: "Sad",
  angry: "Angry",
  fearful: "Fearful",
  disgusted: "Disgusted",
  surprised: "Surprised",
};
export const SUGGESTION_UNAVAILABLE = "SUGGESTION_UNAVAILABLE";
export const UNAVAILABLE_REASONS = [
  "NO_FACE",
  "MULTIPLE_FACES",
  "CAMERA_OFF",
  "MODEL_ERROR",
  "BUSY",
  "LOW_QUALITY",
  "READING_UNAVAILABLE",
  "GAP",
];
export const UNAVAILABLE_LABELS = {
  NO_FACE: "No face detected",
  MULTIPLE_FACES: "Multiple faces detected",
  CAMERA_OFF: "Camera off",
  MODEL_ERROR: "Model unavailable",
  BUSY: "Detector busy",
  LOW_QUALITY: "Low-quality frame",
  READING_UNAVAILABLE: "Reading unavailable",
  GAP: "Missing samples",
};

// ponytail: provisional blendshape thresholds; validate/tune on target devices before claiming accuracy.
export const MOVEMENT_THRESHOLDS = {
  smile: 0.4,
  brow_raise: 0.4,
  brow_furrow: 0.4,
  lip_corners_lowered: 0.4,
};

const EMPTY_COUNTS = () => Object.fromEntries(MOVEMENTS.map(movement => [movement, 0]));
const EMPTY_UNAVAILABLE = () => Object.fromEntries(UNAVAILABLE_REASONS.map(reason => [reason, 0]));

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function missingRequiredScores(blendshapes) {
  if (!blendshapes || typeof blendshapes !== "object") return true;
  return ENABLED_MOVEMENTS.some(movement =>
    MOVEMENT_REQUIRED_SCORES[movement].some(name => !finiteNumber(blendshapes[name])),
  );
}

export function detectMovements(blendshapes) {
  if (!blendshapes || typeof blendshapes !== "object") return [];
  const scores = blendshapes;
  const movements = [];
  const smile = average([
    finiteNumber(scores.mouthSmileLeft) ? scores.mouthSmileLeft : 0,
    finiteNumber(scores.mouthSmileRight) ? scores.mouthSmileRight : 0,
  ]);
  if (smile >= MOVEMENT_THRESHOLDS.smile) movements.push("smile");
  const browRaise = Math.max(
    finiteNumber(scores.browInnerUp) ? scores.browInnerUp : 0,
    finiteNumber(scores.browOuterUpLeft) ? scores.browOuterUpLeft : 0,
    finiteNumber(scores.browOuterUpRight) ? scores.browOuterUpRight : 0,
  );
  if (browRaise >= MOVEMENT_THRESHOLDS.brow_raise) movements.push("brow_raise");
  const browFurrow = average([
    finiteNumber(scores.browDownLeft) ? scores.browDownLeft : 0,
    finiteNumber(scores.browDownRight) ? scores.browDownRight : 0,
  ]);
  if (browFurrow >= MOVEMENT_THRESHOLDS.brow_furrow) movements.push("brow_furrow");
  const lipCornersLowered = average([
    finiteNumber(scores.mouthFrownLeft) ? scores.mouthFrownLeft : 0,
    finiteNumber(scores.mouthFrownRight) ? scores.mouthFrownRight : 0,
  ]);
  if (lipCornersLowered >= MOVEMENT_THRESHOLDS.lip_corners_lowered) {
    movements.push("lip_corners_lowered");
  }
  return movements.filter(movement => ENABLED_MOVEMENTS.includes(movement));
}

export function createObservationState(requestId = null, status = requestId ? "requested" : "idle") {
  return {
    requestId,
    status,
    expected: 0,
    valid: 0,
    counts: EMPTY_COUNTS(),
    unavailableTotal: 0,
    unavailable: EMPTY_UNAVAILABLE(),
    lastSeq: -1,
    lastElapsed: 0,
    slots: [],
    suggestions: {},
    truncated: false,
    startedAt: null,
    finishedAt: null,
    expiresAt: null,
  };
}

export function startCollecting(state, now = Date.now()) {
  if (!state.requestId) return state;
  return {
    ...state,
    status: "collecting",
    startedAt: now,
    finishedAt: null,
    expiresAt: null,
  };
}

export function latestCheck(state) {
  const slot = state.slots[state.slots.length - 1];
  if (!slot) return null;
  if (!slot.valid) {
    return { valid: false, movements: [], unavailable_reason: slot.unavailable_reason };
  }
  return { valid: true, movements: slot.movements, unavailable_reason: null };
}

function validSuggestion(state, suggestion) {
  if (!suggestion || typeof suggestion !== "object" || state.status !== "collecting") return false;
  if (suggestion.request_id !== state.requestId) return false;
  if (!Number.isInteger(suggestion.seq) || suggestion.seq < 0 || suggestion.seq > 86_400) return false;
  const expression = suggestion.suggested_expression;
  const reason = suggestion.unavailable_reason;
  if (expression != null) {
    return SUGGESTED_EXPRESSIONS.includes(expression) && reason == null;
  }
  return reason === SUGGESTION_UNAVAILABLE;
}

export function applySuggestion(state, suggestion) {
  if (!validSuggestion(state, suggestion) || state.suggestions[suggestion.seq]) return state;
  const next = {
    ...state.suggestions,
    [suggestion.seq]: {
      suggested_expression: suggestion.suggested_expression,
      unavailable_reason: suggestion.unavailable_reason,
    },
  };
  const keys = Object.keys(next).map(Number).sort((left, right) => left - right);
  for (const key of keys.slice(0, Math.max(0, keys.length - RING_SIZE))) {
    delete next[key];
  }
  return { ...state, suggestions: next };
}

export function latestSuggestion(state) {
  const slot = state.slots[state.slots.length - 1];
  if (!slot) return null;
  let bestSeq = -1;
  let best = null;
  for (const key of Object.keys(state.suggestions)) {
    const seq = Number(key);
    if (seq <= slot.seq && seq > bestSeq) {
      bestSeq = seq;
      best = state.suggestions[key];
    }
  }
  if (!best) return { status: "missing" };
  if (best.suggested_expression) {
    return { status: "label", expression: best.suggested_expression, seq: bestSeq };
  }
  return { status: "unavailable", seq: bestSeq };
}

export function buildSuggestionStats(state) {
  const counts = Object.fromEntries(SUGGESTED_EXPRESSIONS.map(expression => [expression, 0]));
  let unavailable = 0;
  let missing = 0;
  let total = 0;
  for (const slot of state.slots) {
    if (!slot.valid) continue;
    total += 1;
    const suggestion = state.suggestions[slot.seq];
    if (!suggestion) {
      missing += 1;
    } else if (suggestion.suggested_expression) {
      counts[suggestion.suggested_expression] += 1;
    } else {
      unavailable += 1;
    }
  }
  const leaders = SUGGESTED_EXPRESSIONS.filter(expression => counts[expression] > 0)
    .filter(expression => counts[expression] === Math.max(...SUGGESTED_EXPRESSIONS.map(item => counts[item])));
  const topCount = leaders.length ? counts[leaders[0]] : 0;
  return {
    counts,
    unavailable,
    missing,
    total,
    leaders,
    topCount,
    tied: leaders.length > 1,
    mostCommon: leaders.length === 1 ? leaders[0] : null,
  };
}

function validSlot(state, slot) {
  if (!slot || typeof slot !== "object" || state.status !== "collecting") return false;
  if (slot.request_id !== state.requestId) return false;
  if (!Number.isInteger(slot.seq) || slot.seq < 0 || slot.seq > 86_400) return false;
  if (!Number.isInteger(slot.elapsed_ms) || slot.elapsed_ms < 0 || slot.elapsed_ms > 86_400_000) return false;
  if (typeof slot.valid !== "boolean") return false;
  if (!Array.isArray(slot.movements) || slot.movements.length > MOVEMENTS.length) return false;
  if (new Set(slot.movements).size !== slot.movements.length) return false;
  if (slot.movements.some(movement => !MOVEMENTS.includes(movement))) return false;
  if (slot.valid) {
    return slot.unavailable_reason == null;
  }
  return UNAVAILABLE_REASONS.includes(slot.unavailable_reason)
    && slot.unavailable_reason !== "GAP"
    && slot.movements.length === 0;
}

export function applyObservationSlot(state, slot) {
  if (!validSlot(state, slot) || slot.seq <= state.lastSeq) return state;
  const gap = state.lastSeq < 0
    ? Math.min(slot.seq, RING_SIZE)
    : Math.min(slot.seq - state.lastSeq - 1, RING_SIZE);
  const expected = Math.max(state.expected, slot.seq + 1);
  const counts = { ...state.counts };
  const unavailable = { ...state.unavailable };
  let valid = state.valid;
  let unavailableTotal = state.unavailableTotal + gap;
  if (gap > 0) unavailable.GAP += gap;
  if (slot.valid) {
    valid += 1;
    for (const movement of slot.movements) counts[movement] += 1;
  } else {
    unavailableTotal += 1;
    unavailable[slot.unavailable_reason] += 1;
  }
  const nextSlots = [...state.slots, slot];
  const truncated = state.truncated || nextSlots.length > RING_SIZE;
  return {
    ...state,
    expected,
    valid,
    counts,
    unavailable,
    unavailableTotal,
    lastSeq: slot.seq,
    lastElapsed: slot.elapsed_ms,
    slots: truncated ? nextSlots.slice(-RING_SIZE) : nextSlots,
    truncated,
  };
}

export function finishObservation(state, now = Date.now()) {
  if (state.status !== "collecting") return state;
  return {
    ...state,
    status: "reviewing",
    finishedAt: now,
    expiresAt: now + REVIEW_WINDOW_MS,
  };
}

export function clearObservation() {
  return createObservationState();
}

export function isObservationExpired(state, now = Date.now()) {
  return state.status === "reviewing" && Number.isFinite(state.expiresAt) && now >= state.expiresAt;
}

export function formatPercent(value) {
  if (!finiteNumber(value)) return "0";
  const rounded = Math.round(value * 10) / 10;
  return rounded.toFixed(1).replace(/\.0$/, "");
}

export function formatDuration(ms) {
  if (!finiteNumber(ms) || ms <= 0) return "0 seconds";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds} second${seconds === 1 ? "" : "s"}`;
  const minutes = Math.round(seconds / 60);
  return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}

export function formatElapsed(ms) {
  if (!finiteNumber(ms) || ms < 0) return "0:00";
  const total = Math.floor(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function buildFacts(state, timeline = []) {
  const expected = state.expected;
  const valid = state.valid;
  const eventCounts = Object.fromEntries(MOVEMENTS.map(movement => [movement, 0]));
  for (const event of timeline) {
    if (eventCounts[event.movement] !== undefined) eventCounts[event.movement] += 1;
  }
  const coverage = expected > 0 ? (valid / expected) * 100 : 0;
  const eligible = valid >= SUFFICIENCY_MIN_VALID && coverage >= SUFFICIENCY_MIN_COVERAGE;
  const frequencies = Object.fromEntries(
    MOVEMENTS.map(movement => [
      movement,
      valid > 0 ? (state.counts[movement] / valid) * 100 : 0,
    ]),
  );
  const detected = MOVEMENTS.filter(movement => state.counts[movement] > 0);
  const topCount = detected.length ? Math.max(...detected.map(movement => state.counts[movement])) : 0;
  const leaders = detected.filter(movement => state.counts[movement] === topCount);
  const tie = eligible && leaders.length > 1;
  const predominant = eligible && leaders.length === 1 ? leaders[0] : null;
  const noMovements = valid > 0 && detected.length === 0;
  return {
    expected,
    valid,
    coverage,
    eligible,
    counts: { ...state.counts },
    eventCounts,
    totalEvents: timeline.length,
    frequencies,
    detected,
    predominant,
    leaders,
    tie,
    noMovements,
    unavailableTotal: state.unavailableTotal,
    unavailable: { ...state.unavailable },
    durationMs: state.lastElapsed,
    truncated: state.truncated,
    requestId: state.requestId,
  };
}

function coveragePhrase(facts) {
  return `${facts.valid} of ${facts.expected} scheduled samples were usable (${formatPercent(facts.coverage)}% coverage)`;
}

function unavailablePhrase(facts) {
  return facts.unavailableTotal > 0
    ? `${facts.unavailableTotal} sample${facts.unavailableTotal === 1 ? " was" : "s were"} unavailable.`
    : "";
}

const DISCLAIMER = "Visible movements do not establish the student's emotional state.";

function movementCounts(facts, exclude = null) {
  return MOVEMENTS
    .filter(movement => movement !== exclude && facts.detected.includes(movement))
    .map(movement => `${MOVEMENT_LABELS[movement]} appeared in ${facts.counts[movement]} of ${facts.valid} usable samples (${formatPercent(facts.frequencies[movement])}%)`);
}

function eventSummary(facts) {
  const parts = MOVEMENTS
    .filter(movement => facts.eventCounts[movement] > 0)
    .map(movement => `${MOVEMENT_LABELS[movement]}: ${facts.eventCounts[movement]}`);
  return parts.length ? parts.join("; ") : "none";
}

export function renderObservationSentence(facts) {
  if (!facts || facts.expected === 0) {
    return `No observations collected. Sustained events: none. ${DISCLAIMER}`;
  }
  if (facts.valid === 0 || !facts.eligible) {
    return `Only ${coveragePhrase(facts)}. There is insufficient usable data to identify a most frequently detected movement. Sustained events: ${eventSummary(facts)}. ${DISCLAIMER}`;
  }
  if (facts.noMovements) {
    return `Tracking was usable for ${coveragePhrase(facts)}. No supported movement was detected in these usable samples. This does not establish a neutral emotion. Sustained events: none. ${DISCLAIMER}`;
  }
  const unavailable = unavailablePhrase(facts);
  if (facts.tie) {
    const tied = facts.leaders.map(movement => MOVEMENT_LABELS[movement]).join(" and ");
    return `During the temporary observation period, ${coveragePhrase(facts)}. No single most frequent movement was identified; ${tied} were tied. ${movementCounts(facts).join("; ")}. Sustained events: ${eventSummary(facts)}. ${unavailable} Movements can overlap. ${DISCLAIMER}`.replace(/\s+/g, " ").trim();
  }
  const primary = `${MOVEMENT_LABELS[facts.predominant]} was the most frequently detected movement, appearing in ${facts.counts[facts.predominant]} of ${facts.valid} usable samples (${formatPercent(facts.frequencies[facts.predominant])}%)`;
  const others = movementCounts(facts, facts.predominant);
  return `During the temporary observation period, ${coveragePhrase(facts)}. ${primary}${others.length ? `; ${others.join("; ")}` : ""}. Sustained events: ${eventSummary(facts)}. ${unavailable} Movements can overlap. ${DISCLAIMER}`.replace(/\s+/g, " ").trim();
}

export function renderObservationBullets(facts) {
  if (!facts || facts.expected === 0) {
    return ["No observations collected.", "Sustained events: none.", DISCLAIMER];
  }
  const lines = [
    `Observation period: ${formatDuration(facts.durationMs)}.`,
    `Usable samples: ${facts.valid} of ${facts.expected} (${formatPercent(facts.coverage)}% coverage).`,
  ];
  if (facts.valid === 0 || !facts.eligible) {
    lines.push("Insufficient usable observations to identify a most frequently detected movement.");
  } else if (facts.noMovements) {
    lines.push("No supported movement was detected in usable samples.");
    lines.push("This does not establish a neutral emotion.");
  } else if (facts.tie) {
    lines.push(`No single most frequent movement; ${facts.leaders.map(movement => MOVEMENT_LABELS[movement]).join(" and ")} were tied.`);
    for (const movement of MOVEMENTS.filter(item => facts.detected.includes(item))) {
      lines.push(`${MOVEMENT_LABELS[movement]}: ${facts.counts[movement]} of ${facts.valid} (${formatPercent(facts.frequencies[movement])}%).`);
    }
  } else {
    lines.push(`Most frequently detected movement: ${MOVEMENT_LABELS[facts.predominant]}, ${facts.counts[facts.predominant]} of ${facts.valid} (${formatPercent(facts.frequencies[facts.predominant])}%).`);
    for (const movement of MOVEMENTS.filter(item => item !== facts.predominant && facts.detected.includes(item))) {
      lines.push(`${MOVEMENT_LABELS[movement]}: ${facts.counts[movement]} of ${facts.valid} (${formatPercent(facts.frequencies[movement])}%).`);
    }
  }
  lines.push(`Sustained events: ${eventSummary(facts)}.`);
  if (facts.unavailableTotal > 0) lines.push(`Unavailable samples: ${facts.unavailableTotal}.`);
  lines.push("Movements can overlap.");
  if (facts.truncated) lines.push("The visible timeline is truncated; full-cycle counts are preserved.");
  lines.push(DISCLAIMER);
  return lines;
}

export function buildTimeline(slots) {
  const events = [];
  const streaks = Object.fromEntries(MOVEMENTS.map(movement => [movement, { count: 0, firstMs: 0, event: null }]));
  let previousSeq = -1;
  let previousElapsed = null;
  const close = movement => {
    const streak = streaks[movement];
    if (streak.event) {
      events.push(streak.event);
      streak.event = null;
    }
    streak.count = 0;
    streak.firstMs = 0;
  };
  for (const slot of slots) {
    const elapsedGap = previousElapsed !== null
      && slot.elapsed_ms - previousElapsed > ELAPSED_EVENT_GAP_MS;
    if (slot.seq > previousSeq + 1 || elapsedGap) {
      for (const movement of MOVEMENTS) close(movement);
    }
    if (!slot.valid) {
      for (const movement of MOVEMENTS) close(movement);
      previousSeq = slot.seq;
      previousElapsed = slot.elapsed_ms;
      continue;
    }
    for (const movement of MOVEMENTS) {
      const streak = streaks[movement];
      if (slot.movements.includes(movement)) {
        if (streak.count === 0) streak.firstMs = slot.elapsed_ms;
        streak.count += 1;
        if (streak.count === 2) {
          streak.event = {
            movement,
            startMs: streak.firstMs,
            endMs: slot.elapsed_ms,
            samples: 2,
          };
        } else if (streak.event) {
          streak.event.endMs = slot.elapsed_ms;
          streak.event.samples += 1;
        }
      } else {
        close(movement);
      }
    }
    previousSeq = slot.seq;
    previousElapsed = slot.elapsed_ms;
  }
  for (const movement of MOVEMENTS) close(movement);
  return events.sort((left, right) => left.startMs - right.startMs);
}

function summarizeReviewRow(row, suggestions) {
  const counts = Object.fromEntries(SUGGESTED_EXPRESSIONS.map(expression => [expression, 0]));
  let unavailable = 0;
  let missing = 0;
  for (const seq of row.seqs) {
    const suggestion = suggestions[seq];
    if (!suggestion) {
      missing += 1;
    } else if (suggestion.suggested_expression) {
      counts[suggestion.suggested_expression] += 1;
    } else {
      unavailable += 1;
    }
  }
  const leaders = SUGGESTED_EXPRESSIONS.filter(expression => counts[expression] > 0)
    .filter(expression => counts[expression] === Math.max(...SUGGESTED_EXPRESSIONS.map(item => counts[item])));
  return {
    startMs: row.startMs,
    endMs: row.endMs,
    movements: MOVEMENTS.filter(movement => row.movements.has(movement)),
    checks: row.seqs.length,
    suggestion: leaders.length === 1 ? leaders[0] : null,
    tie: leaders.length > 1,
    counts,
    unavailable,
    missing,
  };
}

export function buildReviewRows(state) {
  const rows = [];
  let current = null;
  let previousSeq = -1;
  let previousElapsed = null;
  const close = () => {
    if (!current) return;
    rows.push(summarizeReviewRow(current, state.suggestions));
    current = null;
  };
  for (const slot of state.slots) {
    const elapsedGap = previousElapsed !== null
      && slot.elapsed_ms - previousElapsed > ELAPSED_EVENT_GAP_MS;
    if (slot.seq > previousSeq + 1 || elapsedGap) close();
    if (!slot.valid || slot.movements.length === 0) {
      close();
      previousSeq = slot.seq;
      previousElapsed = slot.elapsed_ms;
      continue;
    }
    if (!current) {
      current = {
        startMs: slot.elapsed_ms,
        endMs: slot.elapsed_ms,
        movements: new Set(),
        seqs: [],
      };
    }
    current.endMs = slot.elapsed_ms;
    current.seqs.push(slot.seq);
    for (const movement of slot.movements) current.movements.add(movement);
    previousSeq = slot.seq;
    previousElapsed = slot.elapsed_ms;
  }
  close();
  return rows;
}
