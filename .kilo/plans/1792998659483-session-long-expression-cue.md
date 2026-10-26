# Session-Long Local Expression Cue — Implementation Plan

**Status:** READY FOR IMPLEMENTATION
**Risk:** HIGH (privacy/AI behavior); **no backend storage, DB, HTTP endpoint, or OpenAPI change**
**Builds on:** the uncommitted expression-cue + indicator work from `.kilo/plans/1792774405483-video-demo-test-button.md`
**Supersedes:** the ~3-second / per-check duration and consent cadence in ADR-009 and ADR-025 only. All other privacy boundaries remain.

## Goal

Let the Counselor start one optional expression cue for an appointment call. The Student
consents once **for that session**. The Student's browser then repeats local ~3-second scans
every ~5 seconds and relays only the current label + confidence until either participant
stops, the call ends, or the Student leaves. No frames, landmarks, embeddings, history, or
trends leave or persist.

## Decisions

1. **Consent cadence:** per session, not per scan. Counselor clicks **Start live expression cue**; Student sees **Allow for this session** / **Decline**. No stored grant.
2. **Cadence:** reuse the existing 10-frame × 300 ms scan (~3 s), then wait ~2 s, then repeat (≈5 s per update). Main thread for v1; move to a worker if the call janks.
3. **Protocol:** unchanged message types. The same `id` stays active for the whole session; multiple `result` and `unavailable` events are allowed. Server allowlist, role matrix, confidence validation, relay-only behavior, and `1008` closes stay as-is.
4. **Current cue only:** each `result` replaces the displayed cue; `unavailable` clears it and shows “No cue is currently shared.” No timestamps, history, trend, or persisted summary.
5. **Stop:** Student **Stop sharing** or Counselor **Stop** sends `stop`, aborts the loop, and clears both sides. Tab hide, call end, and unmount abort; a call-end teardown does not need another message.
6. **Visibility:** make the left session card scrollable on desktop (`lg:overflow-y-auto`) so the cue below the video is reachable on the Counselor layout. Keep the cue under the video; do not move it to the right rail.
7. **ADR:** add ADR-039 recording the client-approved session-long duration and per-session consent; mark only those parts of ADR-009/ADR-025 as superseded.
8. **No backend code change.** Add one backend relay test for repeated `result` messages with the same `id`.
9. **Rate limit check:** one update per ~5 s is ~12 messages/min, well below the existing `call_signal_messages_per_minute` default of 300.

## Files

### Modify

- `frontend/src/components/calls/ExpressionCuePanel.jsx`
  - Replace the single `scan()` call with an abortable loop.
  - Add a small `pause(ms, signal)` helper.
  - Keep `requestId` active after each result/unavailable; clear only on stop/decline/error.
  - Counselor: update the current cue on each matching `result`; clear the cue on `unavailable`; keep **Stop** visible for the session.
  - Student: change **Allow once** to **Allow for this session**; show **Stop sharing** while the loop runs; keep the current cue visible.
  - Remove the now-unused Counselor **Clear** / **Request another check** controls; **Stop** ends the session, after which **Start live expression cue** returns.
  - Copy: live/session wording; keep the non-diagnostic note and “nothing is saved.”
  - Abort checks after every await so stop/tab-hide/unmount cannot write late state.
  - `ponytail:` comment on the main-thread scan loop and worker upgrade path.
- `frontend/src/pages/ScheduledSessionPage.jsx`
  - Change the left session card from `lg:overflow-hidden` to `lg:overflow-y-auto` so the cue is visible on desktop/Counselor layouts.
- `frontend/tests/expression.test.cjs`
  - Update button/copy assertions to session semantics.
  - Add: repeated result updates replace the current cue; `unavailable` clears it without ending the session; Stop aborts the loop; unmount/tab-hide/phase-change abort; no result after stop.
  - Stop or unmount every Student loop so timers do not keep the test process alive.
- `frontend/tests/appointment-call.test.cjs`
  - Update Student “Allow for this session” flow.
  - Counselor: start once, receive two results, assert the cue updates, then Stop clears and sends `stop`.
  - Keep the unknown-role and stop tests.
- `backend/app/tests/integration/test_calls.py`
  - Add a relay test that sends two `result` messages with the same `id` and asserts both reach the other participant. No production backend change.
- `.ai/DECISIONS.md`
  - Add ADR-039: session-long local cue, per-session consent, ~5 s updates, current cue only, stop/tab-hide/call-end abort, no history/storage/SOS effect.
  - Update ADR-009 and ADR-025 to note their duration/consent cadence is superseded by ADR-039; keep all privacy boundaries.
- `docs/AI_EMOTIONAL_BASELINE.md`
  - “One check at a time” → session-long live cue; describe per-session consent, current-only display, no history.
- `docs/AUDIO_VIDEO_CALLS.md`
  - Expression bullet: Counselor starts once, Student consents per session, repeated results, stop either side; still ephemeral.
- `docs/API_CONTRACT.md`
  - Note that `id` may stay active for a session and multiple `result`/`unavailable` messages are valid; no schema/endpoint change.
- `docs/USER_ROLES.md`
  - Student: allow/decline the session-long cue; Counselor: start/stop the consented live cue.
- `.ai/CURRENT_TASK.md`
  - Record this follow-up, verification, and unresolved risks.

### No changes

- No backend production code, migration, table, HTTP endpoint, audit, or OpenAPI change.
- No `localStorage`/IndexedDB, no frame/landmark/embedding upload, no history/trend, no SOS/appointment effect.
- No change to the existing call start/mode/window rules or duplicate-connection handling.

## Ordered tasks

1. Update `ExpressionCuePanel` to session semantics: per-session consent, repeat loop, current-only result, Stop, abort checks.
2. Add `pause` and the `ponytail:` performance comment; ensure no late state writes.
3. Make the left session card scrollable so the cue is visible.
4. Update the frontend tests; add repeated-update, unavailable-clears, stop/abort, and no-late-result cases.
5. Add the repeated-result backend relay test.
6. Update ADR-039/009/025 and the owning docs.
7. Run focused tests, full frontend suite, build, backend calls tests, and OpenAPI check.
8. Fresh read-only HIGH-risk review of the final diff; then two-browser manual check.

## Edge cases

- **Camera off at consent:** Allow disabled; “Turn your camera on to allow this.”
- **Camera off mid-session:** no face → `unavailable` each cycle; Counselor sees no cue; resumes automatically when the camera returns.
- **Low confidence / no face:** no cue displayed; never show a below-0.60 guess.
- **Tab hidden:** abort the loop, send `stop`, clear both sides; a new Counselor request is required to resume.
- **Call end / phase change / unmount:** abort; no further results.
- **Counselor Stop:** Student receives `stop`, aborts, clears.
- **Student Stop:** Counselor clears.
- **Socket send failure:** stop the loop and show a safe “call unavailable” message; call teardown handles the rest.
- **Model/scan failure:** stop the session with a safe alert; do not retry in a tight loop.
- **Late result after stop/unmount:** ignored by the Student abort checks and by the Counselor’s active-id check.
- **Repeated results:** replace the cue; never append history.
- **Long session:** constant memory/state; no arrays of observations.
- **Duplicate connection:** unchanged; the paired call ends as `REPLACED`.

## Verification

- `node --test tests/expression.test.cjs tests/appointment-call.test.cjs`
- `npm test`
- `npm run build`
- Backend `pytest app/tests/integration/test_calls.py -q` with the disposable test DB
- `python scripts/export_openapi.py --check`
- `git diff --check`
- Manual two-browser check: start/allow, live cue updates for several minutes, Decline, Student Stop, Counselor Stop, camera off/on, no face, low confidence, tab hidden, call end. Confirm no outbound frame upload, no persisted cue, and no history.
- Fresh read-only HIGH-risk review before acceptance.

## Assumptions / boundaries

- “Whole session” means **Counselor-started, Student-consented, until stopped or the call ends**, not automatic surveillance from call start.
- The existing uncommitted expression implementation and indicator remain the base; this plan only changes duration, consent cadence, current-only display, visibility, and documentation.
- No unresolved product decisions.
