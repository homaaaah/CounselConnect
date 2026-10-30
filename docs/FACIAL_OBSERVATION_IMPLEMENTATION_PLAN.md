# Facial Observation Prototype — Small-Task Implementation Plan

Date: 2026-10-28. Status: **prototype implemented (ADR-040); smile/brow raise/brow furrow enabled; real-device validation pending**.

Read [FACIAL_OBSERVATION_PROTOTYPE_PLAN.md](FACIAL_OBSERVATION_PROTOTYPE_PLAN.md) and [AI_EMOTIONAL_BASELINE.md](AI_EMOTIONAL_BASELINE.md) first. Follow AGENTS.md and .ai/RULES.md. Execute one task at a time; report changed files, checks actually run, and remaining issues before proceeding. Preserve registration, appointment authorization, text chat and Counselor record behavior.

## Day 1 — Verify integration and prove one observable movement

### Task 1: Inspect executable baseline

Read frontend/src/features/facialObservation/, components/calls/FacialObservationPanel.jsx, features/calls/useAppointmentCall.js, components/calls/AppointmentCallPanel.jsx, pages/ScheduledSessionPage.jsx; backend/app/modules/calls/realtime.py and router.py; their existing tests and frontend/package.json. These paths come from CURRENT_TASK.md and must be confirmed in the checkout.

Run existing focused tests and report baseline failures separately. Confirm current event validation, consent state, abort handling, session teardown and no logging. Do not assume the older documented passing counts still hold.

Done when: actual integration seams and deviations from docs are recorded. No feature changes yet.

### Task 2: Select and validate detector adapter

Evaluate a local landmark/action-unit-capable detector against smile first, then brow raise/furrow if time permits. Review its primary documentation, license, model delivery, runtime compatibility and supported outputs before selecting a dependency. Do not convert face-api happy/sad scores into purportedly observed movements.

Use a single adapter returning validity, movement flags and unavailable reason. Keep frames/coordinates inside the adapter and discard promptly. Test face absent, multiple faces (reject ambiguous input), dim light, glasses, head turns, deliberate movements and talking. Use consenting test volunteers; manually annotate observations without emotion labels. Measure false triggers and missed movements, including talking-related mouth movements. Do not claim general accuracy from a small demonstration.

Done when: one movement is usable on target devices without unacceptable call degradation. If no detector passes, present a clearly labeled simulated timeline demonstration and report live detection as unfinished.

## Day 2 — Consent, transport and memory-only observation

### Task 3: Lock the proposed event schema

Read .ai/NAMING_CONVENTIONS.md before choosing final field names. Reuse the authenticated appointment WebSocket; do not add a database or summary HTTP endpoint. Introduce a versioned observation payload with request ID, sequence, elapsed milliseconds, validity, allowlisted movement flags and bounded unavailable reason. Legacy emotion results cannot be accepted as new observations.

Define maximum message bytes, rate, elapsed range and sequence limits in code/tests. Reject NaN, infinity, negative times, arbitrary labels, unexpected fields, unauthorized senders and stale request IDs. Keep existing appointment/session reauthorization. Enforce an active consent cycle on the server; both clients also reject stale results. Server stores only temporary consent/request state, never observation history.

Done when: backend and frontend contract tests agree. Deploy the matching protocol together; incompatible clients fail closed for observations while ordinary call signaling continues where safe.

### Task 4: Add lifecycle and bounded reducer

Implement the state sequence idle → requested → collecting → reviewing → cleared. Decline returns to idle. Withdrawal/expiry/tab hide/disconnect/auth loss/call end/unmount clear all data. A new attempt uses new consent and ID. Late async detector completion must never repopulate a cleared buffer.

Use one-second proposed cadence, no overlapping jobs, sequence gap handling, per-label aggregate counters and a 7,200-slot ring buffer. Track unavailable slots separately. Implement review expiry and Student withdrawal while review remains open. Clear timers, detector resources and React references on teardown.

Done when: tests cover duplicate events, out-of-order results, aborted async work, truncation and every clearing condition. Calls continue normally when observations are unavailable.

## Day 3 — Timeline and selectable summary

### Task 5: Build pure summary calculations

Implement the formulas, sufficiency gates, overlap/tie handling and display rounding in the product plan. Unit-test the example fixtures, boundary values and no-data cases. Separate sampled frequency from event grouping and any detector score. Keep sorting deterministic.

Done when: no possible input divides by zero or produces an emotion/clinical conclusion.

### Task 6: Render the Counselor UI

Retain the call controls and active sharing indicator. Add a compact observations panel with timestamps, current supported movements, tracking coverage, temporary timeline and Finish observations and review / Stop and clear controls.

Add Sentence / Bullets as an accessible radio group or segmented control. Default to Sentence; keep choice only in component memory. Both renderers consume one immutable facts snapshot; switching changes only formatting. Do not restart the detector, alter data, or make a network request on a style switch.

Show “Temporary — clears within five minutes or when you leave/end this session.” Keep Student results hidden but consent, active status, withdrawal and review notice visible. Do not add an export, screenshot, automatic clinical note or transcript control.

Done when: paired renderer tests assert the same counts, coverage, ranking, limitations and ordering; keyboard and small-screen checks pass.

## Day 4 — Integration, rehearsal and handoff

### Task 7: Verify authorization and absence of persistence

Run the repository's actual focused frontend/backend checks using its normal environment. CURRENT_TASK.md documents these candidate commands; confirm paths/dependencies before executing:

- From frontend: node --test tests/facial-observation.test.cjs tests/appointment-call.test.cjs
- From frontend: npm run build
- From backend: pytest app/tests/integration/test_calls.py

Add focused cases for new reducers/renderers and consent lifecycle. Inspect network, logs and browser storage during a test call. Verify no images or observation history leave the allowed path and no summaries enter the record API. Validate third-party model fetch behavior; serve approved assets locally. No DB migration is expected.

Done when: results distinguish automated tests, manual checks, known baseline failures and untested devices.

### Task 8: Conduct a two-browser demonstration

Use separate Student/Counselor accounts and an authorized online appointment. Demonstrate decline, request/allow, one supported movement, unavailable tracking, timeline, both summary styles, same numbers across styles, review expiry, withdrawal during review and call continuation after observation failure. End the call and confirm no summary is recoverable by navigation or refresh.

Do not describe facial-observation percentages as emotional probability. Show any simulated fixture with a persistent “Simulated data” badge.

Done when: prototype can be demonstrated end-to-end and its limits can be explained in one sentence.

### Task 9: Update implementation status

Update the owning doc, API contract, decisions and current task with exactly what was built, detector/version/threshold rationale, protocol schema, real check results and remaining work. Never copy historic “tests passed” claims into the new completion report. Retain the old ADR as history, mark the target replacement implemented only after verification.

## Schedule and scope control

Four focused days is an estimate assuming the existing call works and a suitable detector is found. Day 1 is the feasibility gate. If delayed, ship one movement and deterministic summaries first; defer additional labels and optional timeline polish. Do not reduce consent, cleanup, authorization or truthfulness to meet the demo date.

No speech recognition, chat sentiment, screenshots, persistent reports, model training pipeline, new service, new database or LLM in this iteration.

