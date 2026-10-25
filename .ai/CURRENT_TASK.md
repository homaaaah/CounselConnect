# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** Session UI: scrollable tab panels, automatic join at the scheduled start, and **Mark as done** moved to the session header.
**Risk:** HIGH (completion action placement); MEDIUM (auto-join); LOW (layout).
**Route:** `appointments` + `messaging` (including `docs/REAL_TIME_MESSAGING.md`), plus the `ui-refactor` safety checklist.

## Objective

On both roles' scheduled-session page, the right tab panel scrolls internally; the open page submits the existing authorized join request once at/after the scheduled start (with a manual retry on failure); and the Counselor's **Mark as done** lives in the page header beside **Mark no-show** instead of the Record panel. The standalone `#session-record/{id}` page's tab content also scrolls.

## Result

- The Counselor session page owns one `useSessionRecordEditor` instance; the Student hook is disabled and never requests `/appointments/{id}/record`.
- The header **Mark as done** appears only after a successful record load, saves the current form first, skips a PUT for an already-`FINAL` record, then calls the unchanged `POST /mark-done`. A rejected completion switches to the Record tab and surfaces the named missing fields.
- An open page (including one already in the lobby) submits the join once at/after `messaging_opens_at`; the automatic attempt is a background request (no idle renewal), and a failure shows the error plus **Retry joining** (a normal user request). A start-boundary background session refresh prevents waiting for the 15-second interval.
- The session page and standalone record page use bounded viewport layouts with independently scrolling tab content. The rail Record panel no longer shows **Mark as done**; the standalone page keeps **Finalize record**/**Reopen for editing**.
- A failed record load now offers an inline **Reload record** control, replacing the implicit refetch that remounting the tab used to provide.

## In scope

- `frontend/src/pages/ScheduledSessionPage.jsx`, `frontend/src/pages/SessionRecordPage.jsx`
- `frontend/src/components/sessionRecords/SessionRecordWorkspace.jsx`
- `frontend/src/features/sessionRecords/useSessionRecord.js`, new `useSessionRecordEditor.js`
- `frontend/src/features/messaging/useAppointmentChat.js`
- `frontend/tests/scheduled-chat.test.cjs`, `frontend/tests/session-records.test.cjs`
- Owning docs and ADR-038.

## Out of scope

- Any backend, API, schema, migration, permission, retention, or student file-visibility change.
- A Files tab on the session page; the Student keeps the `#session-record/{id}` link.
- Replacing the explicit join contract with server-side auto-join on reads.
- The future video-permission/chat-UI layout plan.

## Acceptance criteria

- The Counselor page fetches `/record` once at page level; the Student page never requests `/record`.
- **Mark as done** is in the header (only after a successful record load), saves the current form first, never saves an already-`FINAL` record, then calls the unchanged `/mark-done`; incomplete fields switch to the Record tab and name the fields.
- The Record panel no longer renders **Mark as done**; the standalone page keeps **Finalize record** and **Reopen for editing**.
- An open session page joins automatically once at/after `messaging_opens_at`; a failure shows the error plus **Retry joining** and does not retry on every tick.
- Tab content scrolls inside the panel on desktop and mobile; tablist/link stay outside the scroll area; desktop page does not scroll.
- Focused and full frontend tests, the frontend build, the backend regression, and the OpenAPI check all pass (or gaps are reported).

## Contracts to preserve

| Invariant / user capability | Owning contract and code | Regression test |
|---|---|---|
| Join stays participant/`CONFIRMED`/`ONLINE`/window authorized and records `*_joined_at` | `backend/app/modules/appointments/service.py`, `messaging/service.py` | `test_session_records.py`, `scheduled-chat.test.cjs` |
| Chat send/catch-up/WebSocket and call panel behavior unchanged | `useAppointmentChat.js`, `AppointmentCallPanel` | `scheduled-chat.test.cjs`, `appointment-call.test.cjs` |
| Students never request the record/notepad; finalized assessment only after `COMPLETED` | `useSessionRecord.js` `enabled`, `_record_response` | `session-records.test.cjs`, `test_session_records.py` |
| Mark as done saves first, skips an already-`FINAL` record, and is atomic server-side | `useSessionRecordEditor.markDone`, `mark_session_done` | `scheduled-chat.test.cjs`, `test_session_records.py` |
| Standalone page keeps Finalize/Reopen; Counselor History keeps status-only Mark completed | `SessionRecordPage`, `SessionRecordWorkspace` variant | `session-records.test.cjs`, `appointments.test.cjs` |

- Compatible API methods, paths, payload fields, and response shapes: no change.
- Navigation and actions that must remain available: Student files link, Mark no-show, Reopen, Finalize on the standalone page.
- Required integration/browser checks and prerequisites: MySQL test URL for backend regression; manual two-role QA for time-dependent auto-join and layout.
- Intentional behavior changes explicitly authorized by the user: auto-join at start (still an authorized background request), header placement, internal scrolling.

## Verification (run)

- `node --test frontend/tests/scheduled-chat.test.cjs frontend/tests/session-records.test.cjs`: **14 passed**.
- `npm --prefix frontend test`: **121 passed**.
- `npm --prefix frontend run build`: succeeded.
- `pytest app/tests/integration/test_session_records.py app/tests/integration/test_appointments.py app/tests/integration/test_appointments_frontend.py -q` (with `COUNSELCONNECT_TEST_DATABASE_URL`): **83 passed, 1 skipped**. Skip reason: `test_appointments.py:327` "Manila already rolled to the next day for this slot time" (time-dependent, not a missing DB).
- `pytest app/tests --ignore=app/tests/integration/test_calls.py -q`: **260 passed**.
- `test_calls.py`: 19 tests passed in-file, then the file run hung on the peer-disconnect test; the remaining 4 tests (including that test) pass when run individually/groups. The suite's call behaviors are covered, but the full-file run is a reproducible environment hang unrelated to this frontend change.
- `python -B scripts/export_openapi.py --check`: matches the application.
- Fresh read-only HIGH-risk review performed; MEDIUM findings (start-boundary cached capabilities, Notes editing during save, failed-record recovery) and LOW test-strength gaps were fixed and covered.

## Remaining risks / limitations

- Manual QA has not been run in this session: both roles, pre-start/post-start entry, mobile/desktop panel scrolling, join failure retry, and header save-first/incomplete-field behavior still need a browser pass.
- Auto-join is still one authorized request; the only new behavior is who submits it (the open page) and that the automatic attempt does not renew idle activity.
- The full `test_calls.py` file run hangs in this environment at the peer-disconnect test; individual/groupped runs pass. Frontend changes do not touch call signaling.
- `docs/DATABASE.md` was not edited (no schema change; it still carries the earlier reopen wording owned by the prior task).
- UI disabling is cosmetic; the server remains authoritative.
