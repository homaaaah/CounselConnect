const assert = require("node:assert/strict");
const { test } = require("node:test");

require("./register-app.cjs");

const {
  ENABLED_MOVEMENTS,
  MOVEMENTS,
  MOVEMENT_LABELS,
  SUGGESTION_LABELS,
  SUGGESTION_UNAVAILABLE,
  applyObservationSlot,
  applySuggestion,
  buildFacts,
  buildReviewRows,
  buildSuggestionStats,
  buildTimeline,
  createObservationState,
  detectMovements,
  finishObservation,
  formatPercent,
  isObservationExpired,
  latestCheck,
  latestSuggestion,
  missingRequiredScores,
  renderObservationBullets,
  renderObservationSentence,
  startCollecting,
} = require("../src/features/facialObservation/observation.js");
const { mapHumanEmotion } = require("../src/features/facialObservation/suggestionModel.js");

const slot = (seq, movements = [], extra = {}) => ({
  request_id: "req-1",
  seq,
  elapsed_ms: seq * 1000,
  valid: true,
  movements,
  ...extra,
});

function collecting() {
  return startCollecting(createObservationState("req-1"));
}

test("movement mapping uses blendshape thresholds for all enabled movements", () => {
  assert.deepEqual(detectMovements({ mouthSmileLeft: 0.9, mouthSmileRight: 0.9 }), ["smile"]);
  assert.deepEqual(detectMovements({ mouthSmileLeft: 0.1, mouthSmileRight: 0.1 }), []);
  assert.deepEqual(detectMovements(null), []);
  assert.deepEqual(MOVEMENTS, ["smile", "brow_raise", "brow_furrow", "lip_corners_lowered"]);
  assert.deepEqual(ENABLED_MOVEMENTS, ["smile", "brow_raise", "brow_furrow", "lip_corners_lowered"]);
  assert.deepEqual(detectMovements({ browInnerUp: 0.9 }), ["brow_raise"]);
  assert.deepEqual(detectMovements({ browDownLeft: 0.9, browDownRight: 0.9 }), ["brow_furrow"]);
  assert.deepEqual(detectMovements({ mouthFrownLeft: 0.9, mouthFrownRight: 0.9 }), ["lip_corners_lowered"]);
  assert.equal(MOVEMENT_LABELS.brow_raise, "Brows raised");
  assert.equal(MOVEMENT_LABELS.brow_furrow, "Brows lowered");
  assert.equal(MOVEMENT_LABELS.lip_corners_lowered, "Lip corners lowered");
});

test("Human emotion labels map to the canonical suggestion labels", () => {
  assert.equal(mapHumanEmotion("angry"), "angry");
  assert.equal(mapHumanEmotion("disgust"), "disgusted");
  assert.equal(mapHumanEmotion("fear"), "fearful");
  assert.equal(mapHumanEmotion("happy"), "happy");
  assert.equal(mapHumanEmotion("sad"), "sad");
  assert.equal(mapHumanEmotion("surprise"), "surprised");
  assert.equal(mapHumanEmotion("neutral"), "neutral");
  assert.equal(mapHumanEmotion("unknown"), null);
});

test("required scores mark a reading unavailable", () => {
  const complete = {
    mouthSmileLeft: 0.1,
    mouthSmileRight: 0.1,
    browInnerUp: 0.1,
    browDownLeft: 0.1,
    browDownRight: 0.1,
    mouthFrownLeft: 0.1,
    mouthFrownRight: 0.1,
  };
  assert.equal(missingRequiredScores(complete), false);
  assert.equal(missingRequiredScores({ ...complete, mouthFrownRight: undefined }), true);
  assert.equal(missingRequiredScores(null), true);
});

test("latest check reflects invalid slots instead of the last valid movement", () => {
  let state = collecting();
  state = applyObservationSlot(state, slot(0, ["smile"]));
  assert.deepEqual(latestCheck(state), { valid: true, movements: ["smile"], unavailable_reason: null });
  state = applyObservationSlot(state, slot(1, [], { valid: false, unavailable_reason: "CAMERA_OFF" }));
  assert.deepEqual(latestCheck(state), { valid: false, movements: [], unavailable_reason: "CAMERA_OFF" });
});

test("slot reducer counts valid, invalid, gaps, duplicates, and out-of-order slots", () => {
  let state = collecting();
  state = applyObservationSlot(state, slot(0, ["smile"]));
  state = applyObservationSlot(state, slot(1, ["smile"]));
  state = applyObservationSlot(state, slot(2, [], { valid: false, unavailable_reason: "NO_FACE" }));
  state = applyObservationSlot(state, slot(4, ["smile"]));
  state = applyObservationSlot(state, slot(4, ["smile"]));
  state = applyObservationSlot(state, slot(2, ["smile"]));

  assert.equal(state.expected, 5);
  assert.equal(state.valid, 3);
  assert.deepEqual(state.counts, { smile: 3, brow_raise: 0, brow_furrow: 0, lip_corners_lowered: 0 });
  assert.equal(state.unavailableTotal, 2);
  assert.equal(state.unavailable.NO_FACE, 1);
  assert.equal(state.unavailable.GAP, 1);
  assert.equal(state.lastSeq, 4);
});

test("slot reducer rejects stale request ids and invalid shapes", () => {
  let state = collecting();
  state = applyObservationSlot(state, slot(0, ["smile"], { request_id: "other" }));
  state = applyObservationSlot(state, slot(0, ["unknown"]));
  state = applyObservationSlot(state, slot(0, [], { valid: false, unavailable_reason: "NOPE" }));
  state = applyObservationSlot(state, slot(0, ["smile"], { valid: false, unavailable_reason: "NO_FACE" }));
  assert.equal(state.expected, 0);
  assert.equal(state.valid, 0);
});

test("finish freezes the review window and expires after five minutes", () => {
  let state = collecting();
  state = applyObservationSlot(state, slot(0, ["smile"]));
  const finished = finishObservation(state, 1_000);
  assert.equal(finished.status, "reviewing");
  assert.equal(finished.expiresAt, 1_000 + 5 * 60 * 1000);
  assert.equal(isObservationExpired(finished, 1_000 + 5 * 60 * 1000 - 1), false);
  assert.equal(isObservationExpired(finished, 1_000 + 5 * 60 * 1000), true);
});

test("facts match the product fixture and both renderers keep the same counts", () => {
  const state = {
    ...collecting(),
    expected: 300,
    valid: 240,
    counts: { smile: 96, brow_raise: 48, brow_furrow: 24, lip_corners_lowered: 0 },
    lastElapsed: 300_000,
  };
  const timeline = [
    { movement: "smile", startMs: 0, endMs: 2_000, samples: 2 },
    { movement: "smile", startMs: 10_000, endMs: 12_000, samples: 2 },
    { movement: "brow_raise", startMs: 20_000, endMs: 22_000, samples: 2 },
  ];
  const facts = buildFacts(state, timeline);
  assert.equal(facts.coverage, 80);
  assert.equal(facts.predominant, "smile");
  assert.equal(formatPercent(facts.frequencies.smile), "40");
  assert.equal(formatPercent(facts.frequencies.brow_raise), "20");
  assert.equal(formatPercent(facts.frequencies.brow_furrow), "10");
  assert.deepEqual(facts.eventCounts, { smile: 2, brow_raise: 1, brow_furrow: 0, lip_corners_lowered: 0 });
  assert.equal(facts.totalEvents, 3);

  const sentence = renderObservationSentence(facts);
  const bullets = renderObservationBullets(facts).join("\n");
  for (const text of [sentence, bullets]) {
    assert.ok(text.includes("240 of 300"));
    assert.ok(text.includes("80% coverage"));
    assert.ok(text.includes("Smile"));
    assert.ok(text.includes("96"));
    assert.ok(text.includes("Brows raised"));
    assert.ok(text.includes("48"));
    assert.ok(text.includes("Sustained events:"));
    assert.ok(text.includes("Visible movements do not establish the student's emotional state."));
  }
  assert.ok(sentence.includes("Smile was the most frequently detected movement"));
  assert.ok(bullets.includes("Most frequently detected movement: Smile"));
  assert.ok(sentence.includes("Smile: 2"));
  assert.ok(sentence.includes("Brows raised: 1"));
});

test("insufficient data, no movement, ties, and no data suppress the wrong claims", () => {
  const insufficient = buildFacts({
    ...collecting(),
    expected: 120,
    valid: 12,
    counts: { smile: 3, brow_raise: 0, brow_furrow: 0, lip_corners_lowered: 0 },
  });
  const insufficientText = renderObservationSentence(insufficient);
  assert.ok(insufficientText.includes("Only 12 of 120"));
  assert.ok(insufficientText.includes("insufficient usable data"));
  assert.ok(!insufficientText.includes("was the most frequently detected movement"));

  const noMovement = buildFacts({
    ...collecting(),
    expected: 100,
    valid: 90,
    counts: { smile: 0, brow_raise: 0, brow_furrow: 0, lip_corners_lowered: 0 },
  });
  const noMovementText = renderObservationSentence(noMovement);
  assert.ok(noMovementText.includes("No supported movement was detected"));
  assert.ok(noMovementText.includes("does not establish a neutral emotion"));
  assert.ok(noMovementText.includes("Visible movements do not establish"));

  const tie = buildFacts({
    ...collecting(),
    expected: 100,
    valid: 100,
    counts: { smile: 10, brow_raise: 10, brow_furrow: 0, lip_corners_lowered: 0 },
  });
  const tieText = renderObservationSentence(tie);
  assert.ok(tieText.includes("were tied"));
  assert.ok(!tieText.includes("Smile was the most frequently detected movement"));

  const empty = renderObservationSentence(buildFacts(createObservationState()));
  assert.ok(empty.includes("No observations collected."));
});

test("timeline groups only after two positive slots and closes on a negative or gap", () => {
  const slots = [
    slot(0, ["smile"]),
    slot(1, ["smile"]),
    slot(2, ["smile"]),
    slot(3, []),
    slot(5, ["smile"]),
    slot(6, ["smile"]),
  ];
  const events = buildTimeline(slots);
  assert.equal(events.length, 2);
  assert.equal(events[0].movement, "smile");
  assert.equal(events[0].startMs, 0);
  assert.equal(events[0].endMs, 2000);
  assert.equal(events[1].startMs, 5000);
});

test("elapsed gaps over two seconds and isolated positives do not create an event", () => {
  assert.equal(buildTimeline([
    slot(0, ["smile"]),
    slot(1, ["smile"], { elapsed_ms: 15_000 }),
  ]).length, 0);
});

test("overlapping movements form separate events", () => {
  const events = buildTimeline([
    slot(0, ["smile", "brow_raise"]),
    slot(1, ["smile", "brow_raise"]),
    slot(2, ["smile"]),
  ]);
  assert.equal(events.length, 2);
  assert.deepEqual(events.map(event => event.movement).sort(), ["brow_raise", "smile"]);
  assert.equal(events.find(event => event.movement === "smile").endMs, 2_000);
  assert.equal(events.find(event => event.movement === "brow_raise").endMs, 1_000);
});

test("alternating positive and negative checks keep counts but have zero events", () => {
  let state = collecting();
  const slots = [];
  for (let seq = 0; seq < 10; seq += 1) {
    const next = slot(seq, seq % 2 === 0 ? ["smile"] : []);
    slots.push(next);
    state = applyObservationSlot(state, next);
  }
  const events = buildTimeline(slots);
  const facts = buildFacts(state, events);
  assert.equal(facts.counts.smile, 5);
  assert.equal(facts.eventCounts.smile, 0);
  assert.equal(facts.totalEvents, 0);
  assert.ok(renderObservationSentence(facts).includes("Sustained events: none"));
});

test("percent display rounds to one decimal and trims .0", () => {
  assert.equal(formatPercent(40), "40");
  assert.equal(formatPercent(12.34), "12.3");
  assert.equal(formatPercent(12.05), "12.1");
  assert.equal(formatPercent(0), "0");
});

const suggestion = (seq, expression, requestId = "req-1") => ({
  request_id: requestId,
  seq,
  suggested_expression: expression ?? null,
  unavailable_reason: expression ? null : SUGGESTION_UNAVAILABLE,
});

test("suggestions align by seq and stay separate from movement facts", () => {
  let state = collecting();
  state = applyObservationSlot(state, slot(0, ["smile"]));
  state = applySuggestion(state, suggestion(0, "happy"));
  state = applyObservationSlot(state, slot(1, ["smile", "brow_raise"]));
  state = applySuggestion(state, suggestion(1, "happy"));
  state = applyObservationSlot(state, slot(2, []));
  state = applyObservationSlot(state, slot(3, ["smile"]));
  state = applySuggestion(state, suggestion(3, null));
  state = applyObservationSlot(state, slot(4, ["smile"]));

  const rows = buildReviewRows(state);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0].movements, ["smile", "brow_raise"]);
  assert.equal(rows[0].suggestion, "happy");
  assert.equal(rows[0].checks, 2);
  assert.equal(rows[1].movements[0], "smile");
  assert.equal(rows[1].suggestion, null);
  assert.equal(rows[1].unavailable, 1);
  assert.equal(rows[1].missing, 1);

  const stats = buildSuggestionStats(state);
  assert.equal(stats.total, 5);
  assert.equal(stats.counts.happy, 2);
  assert.equal(stats.unavailable, 1);
  assert.equal(stats.missing, 2);
  assert.equal(stats.mostCommon, "happy");
  assert.equal(stats.tied, false);
  assert.deepEqual(latestSuggestion(state), { status: "unavailable", seq: 3 });
  state = applySuggestion(state, suggestion(4, "happy"));
  assert.deepEqual(latestSuggestion(state), { status: "label", expression: "happy", seq: 4 });
  assert.equal(SUGGESTION_LABELS.happy, "Happy");
});

test("suggestion ties and invalid suggestions fail closed", () => {
  let state = collecting();
  state = applyObservationSlot(state, slot(0, ["smile"]));
  state = applyObservationSlot(state, slot(1, ["smile"]));
  state = applySuggestion(state, suggestion(0, "happy"));
  state = applySuggestion(state, suggestion(1, "sad"));
  const stats = buildSuggestionStats(state);
  assert.equal(stats.tied, true);
  assert.equal(stats.mostCommon, null);
  assert.equal(buildReviewRows(state)[0].tie, true);

  const before = { ...state.suggestions };
  state = applySuggestion(state, suggestion(2, "happy", "other"));
  state = applySuggestion(state, suggestion(0, "happy"));
  state = applySuggestion(state, {
    request_id: "req-1", seq: 2, suggested_expression: "elated", unavailable_reason: null,
  });
  state = applySuggestion(state, {
    request_id: "req-1", seq: 2, suggested_expression: "happy", unavailable_reason: SUGGESTION_UNAVAILABLE,
  });
  state = applySuggestion(state, {
    request_id: "req-1", seq: 2, suggested_expression: null, unavailable_reason: null,
  });
  assert.deepEqual(state.suggestions, before);

  const reviewing = finishObservation(state, 1_000);
  const afterReview = applySuggestion(reviewing, suggestion(2, "happy"));
  assert.deepEqual(afterReview.suggestions, reviewing.suggestions);
});
