# Facial Observation Prototype — Product and Summary Plan

Project: **CounselConnect: A Student Guidance and Counseling System with AI-Assisted Facial Expression Analysis**

Date: 2026-10-28. Status: **prototype implemented (ADR-040); smile/brow raise/brow furrow enabled; real-device validation pending**.
Owning contract: [AI_EMOTIONAL_BASELINE.md](AI_EMOTIONAL_BASELINE.md).
Build sequence: [FACIAL_OBSERVATION_IMPLEMENTATION_PLAN.md](FACIAL_OBSERVATION_IMPLEMENTATION_PLAN.md).

## 1. Goal and scope

Provide the assigned Counselor with optional, timestamped observations of visible facial movements during an authorized online appointment. The Counselor interprets these alongside the conversation and writes their own assessment. Keep the prototype small: one local detector adapter, one temporary event buffer, one deterministic aggregate, and two renderers.

Initial candidate labels: **smile detected**, **brow raise detected**, and **brow furrow detected**. Enable each only after the detector can actually measure and distinguish that movement in a small validation exercise. Start with one reliable label if necessary. No happy/sad/angry labels or psychological conclusions. Do not simply rename the current emotion-classifier outputs to movement labels.

“Not detected” means none of the supported movements met their thresholds; it does not mean neutral emotion. “Unable to observe” means tracking or processing failed. Keep these distinct. Do not infer attention, engagement, cooperation, distress, improvement, or counseling effectiveness.

## 2. Current baseline versus target

Repository docs retrieved 2026-10-28 describe ADR-039: Student-device face-api emotion classification, repeated scans, Counselor-only current label/confidence, and no event history. This documentation review does not independently validate executable source or prior test results.

The target replaces the emotion inference path with a detector of visible movements; adds a bounded in-memory timeline and factual summary; and retains the existing appointment call, authorization, consent, local processing, and Counselor-only result visibility. No new database, HTTP summary endpoint, cloud model, or LLM is needed.

## 3. User flow and consent

1. Student and assigned Counselor join their authorized online call.
2. Counselor selects Request facial observations and acknowledges that observations are optional and do not establish emotion.
3. Student sees what is detected, who sees results, temporary retention, and how to stop. Choices: Allow for this session / Decline. Ordinary counseling remains available either way.
4. Start processing only after explicit consent for this request. Camera permission alone is insufficient.
5. Both participants see an active indicator and Stop sharing. Student sees status and controls, not the observation results; Counselor sees current observations and timeline.
6. Counselor may select Finish observations and review. Student is told sharing has finished. Freeze the Counselor's temporary snapshot for the bounded review period below.
7. Counselor selects **Sentence** or **Bullets**. Default: Sentence. Switching is immediate, recalculates nothing, and does not rescan or send another request.
8. Counselor independently writes any assessment in the existing records workflow. Never autofill, auto-save, attach, or export the AI summary into that record.

Consent copy: “With your permission, your device will detect selected visible facial movements during this call and share observation data with your assigned Counselor. These observations do not determine how you feel. The Counselor can view a temporary timeline and summary. No images or observation history are saved. You can decline or stop without losing access to counseling.”

## 4. Lifecycle and retention

No screenshots, camera recordings, audio analysis, transcript, persisted landmarks, embeddings, database rows, browser storage, analytics, or logs containing observations. Temporary detector coordinates may exist only during local computation and must be discarded immediately after deriving movement flags.

- Student Stop sharing / withdrawal: stop detector, relay revocation, clear buffers and summaries on both clients. No review snapshot survives withdrawal.
- Counselor Stop and clear: same clearing behavior.
- Counselor Finish observations and review: stop detector and freeze an in-memory Counselor snapshot. It remains only in the current authorized session page for **up to five minutes**, or until navigation, refresh, logout, authorization loss, withdrawal, tab hiding, disconnect, call end, or appointment completion, whichever occurs first.
- Review happens before Mark as done / call teardown. Completion clears it immediately; do not promise a durable post-call report.
- Missing face, disabled camera, or unusable frame: record only an unavailable reason/count; never substitute a facial label.
- Tab hiding, disconnect, or model failure: terminate observation and clear data; a new attempt needs fresh consent.
- Closing the observation popover alone must not stop processing; active indicator remains visible.

Five minutes is a proposed prototype implementation default, not an existing repository policy. Keep a visible expiry notice. No observation data is restored after refresh or reconnect.

## 5. Sampling and temporary data

Proposed starting cadence: one analysis slot per second with no concurrent detector jobs. If inference is still busy, mark the slot unavailable rather than queueing frames. Tune cadence only after measuring call performance.

The Student derives movement flags locally. Send only bounded, schema-validated observation/quality data to the assigned Counselor. Never send frames or landmark coordinates. Use a fresh request ID for each consent cycle, monotonically increasing sequence numbers, and elapsed milliseconds from consent; wall-clock timestamps are unnecessary for the timeline.

Per slot: request ID, sequence, elapsed milliseconds, valid flag, movement flags (possibly several), and an allowlisted unavailable reason when needed. Do not invent a confidence value for a geometric heuristic. A model score, if exposed, must be labeled “detector score,” with its meaning documented; it is not emotional certainty or measured accuracy.

Use a 7,200-slot ring buffer (two hours at the initial cadence); retain aggregate counts separately in memory for the full current consent cycle. At the cap, drop oldest timeline slots, label the visible timeline as truncated, and preserve honest full-cycle counts. No unbounded per-frame arrays. Count duplicates only once. Treat sequence gaps as unavailable slots; do not accept a later replay to silently rewrite already finalized counts.

## 6. Calculation rules

Let E = expected scheduled analysis slots during the active consent cycle, including skipped or missing slots; V = valid slots; and C(label) = valid slots in which that movement was detected.

- Coverage = 100 × V / E. If E = 0, show “No observations collected.”
- Movement frequency = 100 × C(label) / V. If V = 0, show “Insufficient usable observations,” with no percentages or predominant label.
- Round displayed percentages to one decimal place, trimming a trailing .0. Preserve integer counts.
- Labels can co-occur; percentages need not total 100%. Explain this beside the distribution.
- Never call frequency a confidence score or a percentage of the student's emotion.
- Report “most frequently detected movement,” not “most likely emotion.”
- Prototype sufficiency gate: at least 30 valid slots and 50% coverage before a predominant label or trend is shown. These are engineering defaults to test, not scientific validity claims.
- If all movement counts are zero, say “No supported movement was detected in usable samples.”
- Exact count ties produce “No single most frequent movement; X and Y were tied.” Do not break ties arbitrarily.
- Low coverage suppresses ranking; show counts and the limitation.
- Do not claim continuous duration from sample counts.

For timeline display, combine consecutive positive slots for a label into one event only after two successive positive slots. Close on the first negative/unavailable/gap. The aggregate frequency still uses individual slots, independently of display grouping. This avoids event-count frequency inflation. Show sample times as approximate observations, not exact movement onset/duration. Thresholds for movement detection must be validated and versioned; temporal grouping alone does not validate a detector.

## 7. One summary object, two renderers

Create a pure aggregate function and a pure facts builder. The facts object contains collection interval, E/V/coverage, movement counts/frequencies, eligibility, predominant/tie outcome, unavailable reasons, and timeline truncation. Render the same ordered facts as a paragraph or a bullet list. Use fixed templates; no generative API.

Use the heading **Facial observation summary**. Always include usable coverage and the statement “Visible movements do not establish the student's emotional state.” No assessment field is generated.

Illustrative fixture, not a real Student result: 300 scheduled samples, 240 valid (80% coverage); smile 96/240 (40%); brow raise 48/240 (20%); brow furrow 24/240 (10%). Remaining samples may have none of these; labels can overlap.

### Sentence style

During the five-minute observation period, 240 of 300 scheduled samples were usable (80% coverage). Smile was the most frequently detected movement, appearing in 96 of 240 usable samples (40%); brow raise appeared in 48 of 240 usable samples (20%) and brow furrow in 24 of 240 (10%). Sixty samples were unavailable. Movements can overlap. Visible movements do not establish the student's emotional state.

### Bullet style

- Observation period: five minutes.
- Usable samples: 240 of 300 (80% coverage).
- Most frequently detected movement: smile, 96 of 240 usable samples (40%).
- Other movements: brow raise, 48 of 240 (20%); brow furrow, 24 of 240 (10%).
- Unavailable samples: 60.
- Movements can overlap.
- Visible movements do not establish the student's emotional state.

Both styles must preserve these same facts. Do not omit a count or limitation to shorten one style.

### Insufficient data

Sentence: “Only 12 of 120 scheduled samples were usable (10% coverage). There is insufficient usable data to identify a most frequently detected movement. Visible movements do not establish the student's emotional state.”

Bullets: the same three facts as three bullets. Suppress predominant labels and trends in both styles.

### No supported movement

“Tracking was usable for 90 of 100 scheduled samples (90% coverage). No supported movement was detected in these usable samples. This does not establish a neutral emotion.”

## 8. Acceptance criteria

- Consent refusal leaves calls and chat functional; no detector runs before consent.
- Every result is scoped to the active appointment, request and assigned pair.
- Withdrawal, expiry and lifecycle cleanup remove both the timeline and summary.
- Counts, rounding, ordering and limitations match in Sentence and Bullets.
- Test zero samples, zero valid samples, sparse coverage, no movements, tied leaders, overlapping labels, missing/duplicate/out-of-order events and buffer truncation.
- No model-derived claim becomes an assessment or affects SOS, appointment outcomes or Student access.
- No imagery, observation payloads or summaries appear in server logs, storage, browser storage, network calls to third parties or clinical-record requests.
- Keyboard users can switch style; status and expiry text remain readable on narrow screens.
- The demonstration labels prerecorded fixtures as simulated. Report real-device checks separately.

## 9. Deferred work

Screenshots, persistence, report export, speech recognition, chat sentiment analysis, self-report check-ins, multimodal inference and diagnostic conclusions are outside this prototype. Any later proposal needs its own scope and evaluation; combining inputs does not by itself establish better accuracy.

## References and authority

Reviewed current Drive copies of AGENTS.md; .ai/RULES.md, CURRENT_TASK.md, CONTEXT_MAP.md and DECISIONS.md; docs/AI_EMOTIONAL_BASELINE.md, AUDIO_VIDEO_CALLS.md, API_CONTRACT.md, SECURITY.md, USER_ROLES.md, WORKFLOWS.md, SYSTEM_OVERVIEW.md, README.md and CounselConnect_Advisor_Revision_Summary.md. Source copies were last modified 2026-10-28. The latest user instruction adds a Sentence/Bullets option. Historical ADR-039 describes existing behavior; this plan describes its targeted successor, not an implemented migration.

