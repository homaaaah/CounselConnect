# Facial Observation Prototype — Implementation Plan

**Status:** COMPLETED (prototype; real-device smile validation pending)
**Risk:** HIGH (privacy/AI behavior; replaces the ADR-039 emotion-cue path)
**Source of truth:** `docs/FACIAL_OBSERVATION_PROTOTYPE_PLAN.md` and
`docs/FACIAL_OBSERVATION_IMPLEMENTATION_PLAN.md`
**Supersedes:** the completed session-long emotion-cue plan in this file.

## Goal

Give the assigned Counselor optional, temporary observations of selected visible facial
movements during an authorized online appointment. The Student's device detects movements
locally; only bounded observation slots reach the Counselor over the existing appointment
call WebSocket. The Counselor sees a temporary timeline and a deterministic Sentence/Bullets
summary for up to five minutes, interprets it alongside the conversation, and writes their
own assessment. The Student sees consent, active status, and Stop controls, not results.

No screenshots, frames, landmarks, embeddings, recordings, transcripts, cloud calls, LLM,
database rows, HTTP summary endpoint, browser storage, analytics, or observation history.

## Decisions

1. **Detector:** MediaPipe Face Landmarker (`@mediapipe/tasks-vision`) with blendshapes,
   loaded lazily on the Student's device. Serve the pinned WASM/model assets locally
   (`frontend/public/mediapipe/`); verify the package/model license and model card before
   committing. No CDN and no third-party fetch.
2. **Scope gate:** validate **smile first**. Add `brow_raise` / `brow_furrow` only if smile
   passes validation and time permits. Never rename face-api `happy/sad/...` scores into
   movement labels. If no movement passes, ship a clearly labeled simulated timeline
   demonstration and report live detection as unfinished.
3. **Mapping:** smile from `mouthSmileLeft`/`mouthSmileRight`; brow raise from
   `browInnerUp`/`browOuterUp*`; brow furrow from `browDownLeft`/`browDownRight`. Thresholds
   live in one versioned config. Detector scores, if exposed, are labeled “detector score,”
   never emotional confidence.
4. **Protocol:** new WS type `facial-observation`, `version: 1`, `event` one of
   `request | consent | decline | observation | finish | stop`. `observation` carries
   `request_id`, `seq`, `elapsed_ms`, `valid`, `movements: string[]`, and an allowlisted
   `unavailable_reason` when invalid. Control events carry `request_id`. No extra fields.
5. **Server:** validate schema, size/rate, roles, request id, sequence/elapsed bounds,
   movement allowlist, and unavailable reasons. Enforce an active consent cycle in the
   existing in-memory `CallRoomRegistry`: `request`/`finish` = Counselor;
   `consent`/`decline`/`observation` = Student; `stop` = either. Clear consent/request state
   on stop, finish, decline, leave, duplicate-connection replacement, and call end. Stale or
   out-of-consent observations are dropped without closing the call; malformed payloads or
   role violations close with `1008`. Never log observation payloads.
6. **Lifecycle:** Student detector starts only after explicit consent, at ~1 slot/second with
   no overlapping jobs. A busy/absent face/camera/model failure becomes an `invalid` slot
   with a bounded reason, never a movement. Student withdrawal, Counselor stop/finish, tab
   hide, auth loss, call end, and unmount abort and clear. Counselor finish freezes an
   in-memory snapshot for five minutes; review happens before call teardown. New attempt =
   new consent and request id.
7. **Counselor data:** reducer accepts only the active request id, ignores duplicates and
   out-of-order events, treats sequence gaps as unavailable slots, keeps a 7,200-slot ring
   buffer, and maintains full-cycle counts separately. Timeline groups two consecutive
   positive slots into one event; aggregate frequency uses individual slots.
8. **Summary:** one immutable facts object, two pure renderers (Sentence default, Bullets
   switch). Include interval, expected/valid/coverage, counts/frequencies, eligibility,
   predominant/tie outcome, unavailable counts, truncation, and “Visible movements do not
   establish the student's emotional state.” No generated text.
9. **UI:** replace `ExpressionCuePanel` with a facial-observation panel in the existing
   in-call popover/control. Student sees consent copy, active/unavailable/finished status,
   and Stop; never results. Counselor sees current movements, coverage, temporary timeline,
   Finish/Stop, Sentence/Bullets, and a five-minute expiry notice. Closing the popover does
   not stop processing; the active control indicator remains. No export or record autofill.
10. **Replacement:** remove the 7-label expression model, allowlist, panel, badge, tests,
    face-api dependency, and weights after the new path is verified. Keep ADR-039 as history
    and record the replacement when implementation is verified. No dual protocol.

## Files

### Frontend

- `frontend/package.json`, `frontend/package-lock.json`: add `@mediapipe/tasks-vision`.
- `frontend/public/mediapipe/`: pinned WASM runtime, `face_landmarker.task`, and a README
  recording version/license/source. Verify sizes and local serving.
- `frontend/src/features/facialObservation/observation.js`: allowlists, versioned threshold
  config, blendshape-to-movement mapping, slot validation, reducer/ring-buffer helpers,
  aggregate/facts builder, Sentence/Bullets renderers.
- `frontend/src/features/facialObservation/observationModel.js`: lazy MediaPipe loader and
  detector adapter. Frames/landmarks stay inside; return only validity, movements, reason.
- `frontend/src/components/calls/FacialObservationPanel.jsx`: consent, detector loop,
  Counselor timeline/review, Sentence/Bullets, stop/finish/expiry, Student status-only view.
- `frontend/src/features/calls/useAppointmentCall.js`: replace expression state/send with
  facial-observation events; keep strict run/socket guards.
- `frontend/src/components/calls/AppointmentCallPanel.jsx`: replace the expression panel,
  control button state, and Counselor-only video badge with observation equivalents.
- `frontend/src/pages/ScheduledSessionPage.jsx`: pass the existing role; no layout change.
- Delete after cutover: `frontend/src/features/expression/`,
  `frontend/src/components/calls/ExpressionCuePanel.jsx`,
  `frontend/public/models/`, `frontend/tests/expression.test.cjs`, and
  `@vladmandic/face-api` from `package.json`/lock.
- `frontend/tests/facial-observation.test.cjs`: pure mapping/reducer/summary/validation tests.
- `frontend/tests/appointment-call.test.cjs`: observation protocol, consent/lifecycle,
  Counselor timeline/summary, Student hidden results, finish/stop/expiry.

### Backend

- `backend/app/modules/calls/realtime.py`: replace expression constants/validation with
  `facial-observation` validation and role rules; add per-room consent/request state.
- `backend/app/modules/calls/router.py`: handle request/consent/decline/observation/finish/
  stop, enforce active consent, relay only to the other participant, clear on teardown.
- `backend/app/tests/integration/test_calls.py`: schema/role/consent/stale/duplicate/gap/
  cleanup/no-audit tests; remove expression tests.

### Docs / state

- `.ai/DECISIONS.md`: record the successor decision; mark ADR-039 superseded only after
  verification. Keep old ADR text as history.
- `.ai/CURRENT_TASK.md`: task state, actual checks, detector version/thresholds, limitations.
- `docs/AI_EMOTIONAL_BASELINE.md`, `docs/AUDIO_VIDEO_CALLS.md`, `docs/API_CONTRACT.md`,
  `docs/USER_ROLES.md`, `docs/README.md`: update only the contracts that change; the two
  facial-observation plans are already present.
- No DB migration, no OpenAPI change, no HTTP endpoint.

## Ordered tasks

1. **Baseline + license gate.** Confirm the current expression seams and tests; run the
   focused frontend/backend checks and record baseline failures. Verify MediaPipe package,
   model, WASM, license, local asset paths, and target-device runtime. Stop if the license or
   runtime is unacceptable.
2. **Smile feasibility gate.** Add the local model assets and a lazy adapter. Implement the
   pure blendshape-to-smile mapping and fixture tests. Validate smile with consenting
   volunteers: absent/multiple faces, dim light, glasses, head turns, talking, deliberate
   smiles. Tune/version thresholds and measure false triggers/misses and call performance.
   If smile fails, switch to the simulated-fixture demonstration and report live detection
   unfinished.
3. **Observation contract.** Read `.ai/NAMING_CONVENTIONS.md`; finalize the v1 field names,
   limits, movement/reason allowlists, and control-event shape. Add backend validation,
   per-room consent state, role rules, stale-drop behavior, cleanup, and tests. Add matching
   frontend send/receive state with strict guards.
4. **Detector lifecycle + reducer.** Implement the ~1/s no-overlap loop, busy/invalid slots,
   sequence/elapsed, abort and cleanup. Implement the Counselor ring buffer, gap/duplicate/
   out-of-order handling, aggregates, timeline grouping, finish freeze, five-minute expiry,
   and withdrawal clearing. Unit-test every clearing and truncation path.
5. **Summary + panel.** Implement the facts builder and Sentence/Bullets renderers from the
   product doc; test zero/insufficient/no-movement/ties/overlap/truncation fixtures. Build
   the Counselor timeline/review and Student status-only UI in the existing popover; add the
   control active state and Counselor-only badge. Verify keyboard, narrow screen, and
   closing-does-not-stop behavior.
6. **Cutover + cleanup.** Remove the old expression model/panel/protocol/tests/dependency/
   assets. Update the owning docs and ADR only after tests pass. Confirm OpenAPI unchanged.
7. **Verification + handoff.** Run focused tests, full frontend, build, backend calls tests,
   OpenAPI check, and `git diff --check`. Perform a fresh HIGH-risk read-only review, then a
   two-browser demonstration covering decline, allow, smile, unavailable tracking, timeline,
   both styles, same numbers, review expiry, withdrawal during review, call continuation,
   and no recoverable data after navigation/refresh. Record simulated vs real-device results
   separately.

## Edge cases

- No face, multiple faces, camera off, dim light, model load error, inference busy, or
  unusable frame: `invalid` with a bounded reason; never a movement or emotion.
- Talking false positives, glasses, head turns, deliberate vs spontaneous movements;
  thresholds are validated/versioned, not treated as accuracy claims.
- Duplicate, out-of-order, missing, or stale request ids/sequences; gaps count as
  unavailable; dropped observations never rewrite finalized counts.
- Zero expected/valid samples; low coverage; 30-valid/50%-coverage gate; no movement; exact
  count ties; overlapping movements; ring-buffer truncation.
- Student withdrawal, Counselor stop/finish, tab hide, auth loss, call end, unmount,
  duplicate connection: abort detector, clear both clients, clear timers/resources.
- Five-minute review expiry; closing the popover; new request after clear; call end during
  review clears immediately.
- Student never sees results; Counselor never gets a record autofill/export/transcript.
- Low-end device performance at ~1 slot/second; no overlapping jobs; call remains usable if
  observations fail.
- No payload logging, audit rows, browser storage, analytics, or third-party requests.

## Validation

- `node --test tests/facial-observation.test.cjs tests/appointment-call.test.cjs`
- `npm test`
- `npm run build`
- Backend `pytest app/tests/integration/test_calls.py -q` with the disposable test DB
- `python scripts/export_openapi.py --check`
- `git diff --check`
- Manual two-browser/device rehearsal from task 7; report simulated data as simulated.
- Fresh read-only HIGH-risk review before acceptance.

## Boundaries

- No diagnostic, emotional-state, attention, engagement, cooperation, distress, or counseling-
  effectiveness claims.
- No persistence, screenshots, recordings, transcripts, cloud inference, LLM, database, or
  HTTP summary endpoint.
- No effect on SOS, appointment outcomes, access, or the clinical record.
- The Student's detector is the only source of observation data; the server is relay-only
  apart from temporary consent/request state.

## Open questions

None for the prototype. The detector path is resolved (MediaPipe, smile first); replacement
of the old expression path and Student status-only visibility follow the source plans.
