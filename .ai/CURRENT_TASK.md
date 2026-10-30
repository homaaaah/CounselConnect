# Current work: Facial observation prototype

## Task: MediaPipe facial observation prototype (2026-10-28)

**Status: COMPLETED (prototype; real-device validation pending).**
**Risk: HIGH** (privacy/AI behavior; replaced the ADR-039 emotion-cue path).
**Source of truth:** `.kilo/plans/1792998659483-session-long-expression-cue.md`;
`docs/FACIAL_OBSERVATION_PROTOTYPE_PLAN.md`;
`docs/FACIAL_OBSERVATION_IMPLEMENTATION_PLAN.md`.

Goal: optional, Counselor-requested, Student-consented local detection of selected visible
movements (smile first), bounded observation slots over the appointment call WebSocket,
Counselor-only temporary timeline + deterministic Sentence/Bullets summary, five-minute
review expiry, no persistence/frames/landmarks/embeddings.

Built: MediaPipe Face Landmarker adapter with local WASM/model assets; smile, brow raise,
and brow furrow enabled at client request (thresholds unvalidated);
`facial-observation` v1 protocol with server-enforced in-memory consent/role state;
Counselor reducer/ring buffer/timeline and Sentence/Bullets summary; Student status-only UI;
in-call popover and Counselor badge; legacy face-api expression path removed.

Verification actually run:
- `node --test tests/facial-observation.test.cjs tests/appointment-call.test.cjs` — 25 passed
- `npm test` — 181 passed, 1 pre-existing calendar failure (`calendar month navigation stays within loaded data`, `frontend/tests/appointments.test.cjs`; known fixture/date drift, unrelated)
- `npm run build` — passed; 102 modules; MediaPipe runtime lazy chunk; local `dist/mediapipe` assets present
- `pytest app/tests/integration/test_calls.py -q` — 40 passed
- `python scripts/export_openapi.py --check` — matches
- `git diff --check` — no errors (LF/CRLF warnings only)

Remaining limitations:
- No real-device validation or two-browser rehearsal was run. Smile, brow raise, and brow
  furrow are enabled at client request, but their thresholds remain unvalidated; disable any
  movement that fails real-device validation.
- Added automated coverage for closing the popover during observation, withdrawal during
  review, and detector failure without ending the call. Review-expiry UI timing, real
  network/log/browser-storage inspection, keyboard/small-screen checks, and model card/license
  approval remain manual.
- MediaPipe runs about once per second on the Student device; no worker offload.
- Review snapshot is in-memory and clears on call-end/navigation as designed; no post-call report.
- The Student device necessarily computes the movement flag to send it; “Counselor-only”
  is a UI and protocol-recipient boundary, not cryptographic blindness.

# Prior work: Session-long local expression cue (ADR-039)

**Status: COMPLETED**
**Risk: HIGH** (privacy/AI behavior); no backend storage, no DB, no HTTP endpoint.
**Route:** `expression-cue` + `calls` (`.ai/CONTEXT_MAP.md`).
**Source of truth:** `.kilo/plans/1792998659483-session-long-expression-cue.md`
(supersedes the duration/consent cadence in `.kilo/plans/1792774405483-video-demo-test-button.md`).

## Follow-up: merge update planning docs (2026-10-28)

**Status: COMPLETED.** Copied the two new facial-observation plans and the target
database v5 snapshot from `CounselConnect(Update)/` and linked the plans from
`docs/README.md`. The unreferenced reviewer/enrollment/notification components and the
live-flow tests were intentionally excluded pending a wiring/test decision. No application
code, migration, or runtime behavior changed.

Verification: all three files present; full frontend suite 189 passed. The SQL snapshot was
not executed against a database; it is a documentation/reference artifact.

## Follow-up: Counselor-only result visibility (2026-10-26)

**Status: COMPLETED.** The Student no longer sees the label/confidence in the panel or the
in-video badge. The Student sees only the live-sharing status and **Stop sharing**; the
Counselor is the only role that sees the result card and badge. No protocol, backend,
storage, or OpenAPI change.

Verification: focused 32 passed; full frontend 189 passed; build passed; tests assert the
Student DOM never contains the result while the Counselor still sees it.

## Follow-up: consent closes popup and activates the icon (2026-10-26)

**Status: COMPLETED.** When the Student accepts, both participants' popovers close and the
face-icon control shows an active emerald ring/title while the cue is live. The popover can
be reopened for Stop/current cue; Stop/decline/tab hide/call end clear the active state.
The in-video result badge remains visible. No backend or protocol change.

Verification: focused 32 passed; full frontend 189 passed; build passed; tests cover
Student accept auto-close, Counselor consent auto-close, active icon title, and stop reset.

## Follow-up: in-video result badge (2026-10-26)

**Status: COMPLETED.** The current expression result is also shown as a small badge inside
the video window for the Counselor only (“Live student cue: …”). The badge updates with each
result and disappears on stop/unavailable or call end. It uses only the already-shared
label/confidence; no new data, storage, or protocol.

Verification: focused 32 passed; full frontend 189 passed; build passed; badge text and
clear-on-stop covered by `appointment-call.test.cjs`.

## Follow-up: expression popup button (2026-10-26)

**Status: COMPLETED.** The expression cue is now a popover over the video, opened by a
face-icon **Expression cue** button in the call controls. The Student's popover auto-opens
on an incoming `request`; either role can close it with X or Escape. Closing keeps the panel
mounted, so an active session-long scan continues. The temporary left-card scroll change was
reverted. No backend, storage, protocol, or OpenAPI change.

Verification: focused expression/call tests 32 passed; full frontend suite 189 passed;
production build passed; `git diff --check` clean apart from LF/CRLF warnings. Tests cover
open/close, Escape, Student auto-open, focusable dialog semantics, and a second result while
the popover is closed.

## Follow-up: session-long expression cue (2026-10-26)

**Status: COMPLETED.** Client requested expression recognition for the whole session.
The Counselor starts one cue; the Student consents **for the session**. The Student's
browser repeats the existing ~3-second local scan every ~5 seconds and relays only the
current label + confidence with the same id until either participant stops or the call
ends. `unavailable` clears the current cue without ending the session. The Counselor's
left session card now scrolls so the cue is reachable on desktop. No backend code, storage,
history, trends, SOS, appointment, or OpenAPI change.

Verification: focused expression/call tests 32 passed; full frontend suite 189 passed;
production build passed (102 modules); backend calls suite 40 passed; OpenAPI matches;
`git diff --check` clean apart from LF/CRLF warnings. A fresh read-only review found one
tab-hide stale-result issue; it was fixed and covered by a new test.

## Follow-up: expression indicator (2026-10-26)

**Status: COMPLETED.** Presentation-only indicator for the already-shared expression cue.
The Counselor result card now shows the matching Font Awesome face icon beside the
observable label and confidence. `expressionLabelIcon` maps the seven labels; unknown labels return
no icon. No backend, protocol, storage, or OpenAPI change.

Verification: focused expression/call tests 30 passed; full frontend suite 187 passed;
production build passed (102 modules).

## Result

The Counselor can start one optional live expression cue during an active appointment call.
The Student sees **Allow for this session** / **Decline**; only after consent does the
Student's browser lazily load `@vladmandic/face-api` (TinyFaceDetector + FaceExpressionNet
weights served from `frontend/public/models/`) and analyze the local call camera. About ten
frames are averaged (~3 seconds), then the browser waits ~2 seconds and repeats until either
participant stops. A cue is displayed to the Counselor only with at least three samples and
a top average of `0.60` or higher; `unavailable` clears the current cue. Only the current rounded label +
confidence is relayed to the other participant over the existing appointment call WebSocket.
Nothing is persisted, audited, logged, or replayed.

Server authority still enforces the expression role matrix (`request` = Counselor;
`consent`/`decline`/`unavailable`/`result` = Student; `stop` = either), event/id/label
allowlists, finite `0..1` confidence, rounding to three decimals, size/rate limits, and
relay-only behavior. Parser-limit `ValueError` also closes with `1008`. The frontend aborts
the loop on Student stop, Counselor stop, tab hide, phase change, and unmount; late or
mismatched results are ignored, low-confidence results are never displayed, and "Shared"
is only claimed when the local WebSocket send succeeds. The cue lives in a popover over the
video, opened from a face-icon control button; closing it does not stop an active scan. The
current cue is also mirrored in a compact badge inside the video window for the Counselor.

## Files changed

Added:
- `frontend/src/features/expression/expression.js`
- `frontend/src/features/expression/expressionModel.js`
- `frontend/src/components/calls/ExpressionCuePanel.jsx`
- `frontend/public/models/` (four weights + `README.md`)
- `frontend/tests/expression.test.cjs`

Modified:
- `backend/app/modules/calls/realtime.py`
- `backend/app/modules/calls/router.py`
- `backend/app/tests/integration/test_calls.py`
- `frontend/package.json`, `frontend/package-lock.json`
- `frontend/src/features/calls/useAppointmentCall.js`
- `frontend/src/components/calls/AppointmentCallPanel.jsx`
- `frontend/src/pages/ScheduledSessionPage.jsx`
- `frontend/tests/appointment-call.test.cjs`
- `docs/AI_EMOTIONAL_BASELINE.md`, `docs/AUDIO_VIDEO_CALLS.md`, `docs/API_CONTRACT.md`, `docs/USER_ROLES.md`
- `.ai/DECISIONS.md` (ADR-039; ADR-009/025 cadence notes), `.ai/CURRENT_TASK.md`
- `.kilo/plans/1792998659483-session-long-expression-cue.md`

No backend production code changed for the session-long follow-up; only its test file was
extended. `frontend/src/App.jsx` and `.kilo/plans/1792774405483-video-demo-test-button.md`
were already modified in the working tree before implementation.

## Verification (all run)

| Check | Result |
|---|---|
| `node --test tests/expression.test.cjs tests/appointment-call.test.cjs` | 32 passed |
| `npm test` (full frontend) | 189 passed |
| `npm run build` | passed, 102 modules; face-api is a lazy 1.33 MB chunk; models copied to `dist/models` |
| `pytest app/tests/integration/test_calls.py` | 40 passed (includes repeated-result relay) |
| `python scripts/export_openapi.py --check` | matches the application (no HTTP change) |
| `python -m py_compile` on modified backend files | passed |
| `git diff --check` | no errors (LF/CRLF warnings only) |
| Fresh read-only HIGH-risk review | found a tab-hide stale-result bug; fixed with `clearExchange()` and a new regression test; final re-review reports no remaining blocker/major |

Full backend suite context (run after the implementation, before the final parser-only fix;
the calls suite was rerun afterward): excluding four modules that fail collection because
`.ai`-unrelated `app/tests/conftest.py` loader functions are missing
(`test_account_screening_scope_migration`, `test_correction_context_migration`,
`test_pending_correction_guard`, `test_registration_release_rehearsal`), the suite produced
**1112 passed, 4 failed, 8 skipped**. The four failures reproduce independently of this
change: `test_live_appointment_screens` (no calendar day shows available times),
two `test_live_management_workflows` UI-state failures, and
`test_users_management::test_safe_sql_paged_search_and_detail` (shared disposable-schema row
drift; 37 Guidance Staff rows instead of 1). These are pre-existing/environmental and were
not modified.

## Limitations

- The real face-api model, camera readiness, session-long scanning, and a two-browser
  start/consent/stop flow were not exercised by automated tests; the tests inject a fake
  scanner. Manual two-browser verification remains human work.
- The live loop runs about three seconds of scanning every five seconds on the main thread;
  move it to a worker if the call visibly janks.
- Popover focus move/return, Escape in a real browser, and screen-reader announcement need a
  manual browser check; `react-test-renderer` has no host refs.
- "Shared" confirms the local WebSocket enqueue, not a peer acknowledgement; there is no
  application-level ack in the call protocol.
- TURN remains static environment configuration and signaling is single-process (unchanged).
- Full backend collection and the four failures above remain pre-existing blockers to a clean
  full-suite result.
- No commit, staging, or push was performed.
