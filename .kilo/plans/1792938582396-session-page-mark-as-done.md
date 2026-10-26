# Session-Page Mark as Done

**Status:** READY FOR IMPLEMENTATION
**Risk:** HIGH (completion/finalization authorization, audit/state transitions)
**Scope:** Counselor scheduled session page only
**No database migration:** reuses `session_records.status`, `session_records.finalized_at`, and `appointments.status`

## Goal

Replace the scheduled session page's **Finalize record** action with one **Mark as done** action in the Record panel. Clicking it saves the current notepad/assessment form, validates all four assessment fields, finalizes the record, and completes the appointment. Keep Counselor History's **Mark completed** and the standalone session record page's **Finalize record** unchanged. Allow a finalized `COMPLETED` record to be reopened.

## Approved decisions

1. The new button lives in the session page's Record panel, replacing **Finalize record**. The session page header's **Mark completed** action is removed; **Mark no-show** stays in the header.
2. All four assessment fields are required. Missing fields return `409 RECORD_INCOMPLETE` with `details.fields`; the appointment stays `CONFIRMED`, the record stays `DRAFT`, and the Counselor sees the missing fields.
3. The Record panel saves the current form first, then calls a new `POST /appointments/{appointment_id}/mark-done`. The server finalizes the record and completes the appointment in one transaction.
4. Scope is the scheduled session page only. Counselor History **Mark completed** remains a status-only action. The standalone `SessionRecordPage`/`SessionRecordWorkspace` keeps **Finalize record** for history-completed drafts and reopened records.
5. A finalized record for a `CONFIRMED` or `COMPLETED` appointment can be reopened. Reopening returns it to `DRAFT`, hides the Student assessment (`404 RECORD_NOT_FOUND`) until re-finalized, and does not re-lock session files.
6. No new appointment/session-record column and no data backfill.

## Contracts to preserve

| Invariant | Owning contract/code | Regression test |
|---|---|---|
| Chat join/send, calls, and video permission behavior are unchanged | `docs/REAL_TIME_MESSAGING.md`, `docs/AUDIO_VIDEO_CALLS.md`; `useAppointmentChat` | `scheduled-chat.test.cjs`, `appointment-call.test.cjs` |
| Student session files remain unavailable before `COMPLETED`; Counselor files work while `CONFIRMED`/`COMPLETED` | `docs/PRIVATE_CLINICAL_DOCUMENTS.md`; `useSessionDocuments`, `SessionRecordWorkspace` | `test_session_records.py`, `session-records.test.cjs` |
| Student sees only a finalized assessment, only after `COMPLETED`; never the notepad | ADR-035; `_record_response`, `SessionRecordWorkspace` | `test_session_records.py`, `session-records.test.cjs` |
| Audit rows contain ids/actors only, never note/assessment text | `SessionRecordService`/`AppointmentsService.audit` | `test_session_records.py` |
| Counselor History completion stays independent of finalization | `docs/COUNSELING_SESSION_RECORDS.md`; `AppointmentsService.transition`, `CounselorHistoryPage` | Existing history/appointment tests |
| `/complete` and `/record/finalize` behavior for existing callers is unchanged | `appointments/router.py`, `service.py` | Existing tests |
| Explicit session join, lobby, call window, and call cleanup are unchanged | `ScheduledSessionPage`, `useAppointmentCall` | `scheduled-chat.test.cjs`, `appointment-call.test.cjs` |

## Backend changes

### 1. Service

`backend/app/modules/appointments/service.py`:

- Add `mark_session_done(self, actor, appointment_id)`:
  - `authorize(actor, ("COUNSELOR",))`; lock the owned appointment with `_locked_owned`.
  - Require `status == "CONFIRMED"`; otherwise `409 INVALID_APPOINTMENT_TRANSITION`.
  - Require the slot start to have passed; otherwise `409 SESSION_NOT_STARTED`.
  - Lock the session record:
    - `None` -> `409 RECORD_NOT_SAVED` ("Open the session record and complete the assessment before marking the session done.").
    - `DRAFT` -> require every `RECORD_FIELDS` value after strip; missing -> `409 RECORD_INCOMPLETE` with `details={"fields": missing}`. Set `FINAL`, set `finalized_at = utcnow()`, and audit `session_record_finalized`.
    - `FINAL` -> skip re-finalization.
  - Complete the appointment: set `COMPLETED`, release the slot, close the linked conversation with `COUNSELOR_OUTCOME`, audit `appointment_completed`, and flush.
  - Do not call `transition("complete")`; History completion must remain status-only. Extract a private completion helper shared by both paths instead of duplicating the slot/conversation/audit side effects.
- Update `reopen_session_record` and `_record_response`:
  - `can_reopen` is true for a `FINAL` record when the appointment is `CONFIRMED` or `COMPLETED`.
  - Reopening sets `DRAFT`, clears `finalized_at`, and audits `session_record_reopened`.
  - A `DRAFT` record remains invisible to the Student; files remain governed by appointment status only.

### 2. Router

`backend/app/modules/appointments/router.py`:

- Add `POST /appointments/{appointment_id}/mark-done`:
  - Counselor-only, no request body.
  - Response: `AppointmentSessionResponse`.
  - Call the service, then `_commit_and_publish(service, appointment, event="session_closed")`, then return `service.session_response(actor, appointment)`.
- Keep `POST /appointments/{appointment_id}/complete` unchanged for Counselor History.
- Keep `POST /appointments/{appointment_id}/record/finalize` for the standalone record page and re-finalization after reopen.
- Stable errors: `409 RECORD_NOT_SAVED`, `409 RECORD_INCOMPLETE` (`details.fields`), `409 SESSION_NOT_STARTED`, `409 INVALID_APPOINTMENT_TRANSITION`, `403 FORBIDDEN_ROLE`, existing 404 for non-participants.

### 3. Generated contract

- Regenerate `contracts/openapi.json`.
- No migration or conftest migration-loader change.

## Frontend changes

### 1. Chat hook

`frontend/src/features/messaging/useAppointmentChat.js`:

- Add `markDone()`:
  - `POST /appointments/${appointmentId}/mark-done`.
  - Replace the local `session` with the returned `AppointmentSessionResponse`.
  - Surface `RECORD_INCOMPLETE` and its `details.fields`; keep the current session on failure.
  - Use the existing `busy`/`error` conventions.
- Add an `appointment-updated` listener that calls `loadSession(true)` when `detail.appointment_id` matches, so the Student/other tab sees completion without waiting for the 15-second refresh. Use the existing `X-Background-Refresh` request and do not renew idle activity.
- Keep `outcome("complete")` for Counselor History.

### 2. Session record workspace

`frontend/src/components/sessionRecords/SessionRecordWorkspace.jsx`:

- Add an optional `onMarkDone` prop.
- In `RecordPanel`, when the workspace is used on the session page (`variant="rail"`) and the user is a Counselor:
  - Render **Mark as done** instead of **Finalize record**.
  - Handler: `const saved = await recordApi.save(form); if (!saved) return; await onMarkDone(); await recordApi.reload();`
  - Disable while `recordApi.saving` or the page's chat action is busy.
  - Show the page's `RECORD_INCOMPLETE` fields error near the button.
- Keep the standalone page (`variant="page"`) unchanged: it still shows **Finalize record** and **Reopen for editing**.
- Keep the notepad/assessment autosave as the single `useSessionRecord` instance; do not add a second editor.

### 3. Session page

`frontend/src/pages/ScheduledSessionPage.jsx`:

- Remove the header **Mark completed** button; keep **Mark no-show**.
- Pass `onMarkDone={chat.markDone}` to the rail `SessionRecordWorkspace`.
- Derive the workspace appointment status from `session.status` (the session response is authoritative after completion) or refetch `GET /appointments/{id}` after success, so Files/assessment visibility updates immediately.
- Keep the Record tab as the place for the notepad and assessment fields; the Mark as done button sits there.
- Show `RECORD_INCOMPLETE` missing fields in the Record tab and/or the page alert.
- Do not add a **Finalize record** button to the session page.

### 4. Unchanged frontend

- `frontend/src/pages/SessionRecordPage.jsx` keeps its finalize action; a finalized `COMPLETED` record now shows **Reopen for editing** because of the backend rule change.
- `frontend/src/pages/counselor/CounselorHistoryPage.jsx` keeps **Mark completed** and calls `/complete`.
- No changes to call/video/permission UI.

## Tests

### Backend

Add to `backend/app/tests/integration/test_session_records.py` and appointment tests:

- `mark-done` with a complete saved record -> record `FINAL`, appointment `COMPLETED`, slot released, linked conversation closed, `session_record_finalized` + `appointment_completed` audits, Student can read the assessment, files unlock.
- Incomplete record -> `409 RECORD_INCOMPLETE` with `details.fields`, appointment stays `CONFIRMED`, record stays `DRAFT`, no finalize audit.
- Missing record -> `409 RECORD_NOT_SAVED`.
- Record already `FINAL` -> appointment completes without a duplicate finalize audit.
- Before scheduled start -> `409 SESSION_NOT_STARTED`; non-Counselor -> 403; other Counselor/Student -> 404.
- `no-show` does not finalize the record.
- Reopen a finalized `COMPLETED` record -> `DRAFT`; Student gets `404 RECORD_NOT_FOUND`; files remain available; re-finalize restores the Student assessment.
- `can_reopen` is true for `CONFIRMED` and `COMPLETED`.
- Counselor History `/complete` still does not finalize (guard the scope decision).

### Frontend

Update `frontend/tests/scheduled-chat.test.cjs`:

- Counselor session page: Record tab shows **Mark as done**, not **Finalize record**.
- Clicking Mark as done saves the form (`PUT /record`) before `POST /mark-done`; success shows the completed/final state and unlocks files.
- Incomplete assessment: mock `409 RECORD_INCOMPLETE`; assert the missing fields are shown and the page stays `CONFIRMED`.
- Header no longer shows **Mark completed**; **Mark no-show** remains.
- Standalone record page still shows **Finalize record**; a finalized `COMPLETED` record shows **Reopen for editing**.
- Counselor History still shows **Mark completed**.

Update `frontend/tests/session-records.test.cjs`:

- Reopen is available for a finalized `COMPLETED` appointment.
- Existing notepad/assessment autosave and finalize tests stay green.

## Documentation

- `docs/COUNSELING_SESSION_RECORDS.md`: session-page Mark as done finalizes and completes; History completion stays independent; reopen allowed for `CONFIRMED`/`COMPLETED`; reopened drafts hide the Student assessment until re-finalized; standalone finalize remains.
- `docs/APPOINTMENT_SCHEDULING.md`: session-page completion behavior and the required tests.
- `docs/API_CONTRACT.md`: `POST /appointments/{id}/mark-done`, response/errors, `can_reopen` rule.
- `docs/PRIVATE_CLINICAL_DOCUMENTS.md`: Mark as done unlocks Student file access; reopening a record does not re-lock files.
- `.ai/NAMING_CONVENTIONS.md`: add the `mark-done` action path if action paths are listed there.
- `.ai/DECISIONS.md`: add the next available ADR after ADR-035 for session-page Mark as done and reopen-after-completion. Coordinate the number with the separate video-call permission plan (which reserves ADR-036); use ADR-037 if that plan lands first.
- `.ai/CURRENT_TASK.md`: risk, scope, preserved contracts, verification, and completion status.
- Regenerate `contracts/openapi.json`.
- Do not edit `docs/DATABASE.md`; there is no schema change.

## Verification

```powershell
# Backend focused + full
& ./backend/.venv/Scripts/python.exe -B -m pytest backend/app/tests/integration/test_session_records.py backend/app/tests/integration/test_appointments.py -q
& ./backend/.venv/Scripts/python.exe -B -m pytest backend/app/tests -q

# Frontend focused + full
node --test frontend/tests/scheduled-chat.test.cjs frontend/tests/session-records.test.cjs
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build

# Generated contract (run from backend/)
& ./.venv/Scripts/python.exe -B scripts/export_openapi.py --check
```

Manual QA:
- Counselor fills all four fields and clicks **Mark as done**: record becomes `FINAL`, appointment `COMPLETED`, Student sees assessment/files.
- Incomplete fields: Mark as done is blocked, appointment stays `CONFIRMED`, fields are named.
- Header **Mark completed** is gone; **Mark no-show** still works.
- History **Mark completed** still completes without finalizing.
- Standalone record page still finalizes a history-completed draft.
- Reopen a finalized `COMPLETED` record: Student loses assessment access, keeps file access; re-finalize restores it.
- Student never sees the Counselor notepad or a `DRAFT` assessment.

## Risks and limitations

- HIGH-risk completion/finalization boundary; the server must remain authoritative even if the button is hidden.
- The session-page-only scope is intentionally inconsistent with History. Do not make History finalize.
- The Record panel's save and the mark-done call are two requests. The finalize+complete step is atomic on the server, but a saved draft can persist if completion then fails. The draft remains invisible to the Student.
- Reopening hides the Student assessment until re-finalization; warn the Counselor and keep files available.
- The notepad/assessment autosave must remain a single hook instance.
- If the separate chat-UI/video-permission plan is implemented later, move the Mark as done control into that plan's session-record card; the backend contract is unchanged.

## Implementation order

1. Backend `mark_session_done` service and router.
2. Backend reopen-after-completion rule.
3. Backend tests and OpenAPI regeneration.
4. Frontend `markDone` hook.
5. `SessionRecordWorkspace` rail Mark as done and session page wiring.
6. Frontend tests.
7. Docs/ADR.
8. Full verification and HIGH-risk review.
