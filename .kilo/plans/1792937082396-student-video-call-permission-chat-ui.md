# Student Video-Call Permission and Chat UI

**Status:** READY FOR IMPLEMENTATION
**Risk:** HIGH (authorization/privacy boundary, schema/migration, session UI redesign)
**Reference UI:** `Reference/chat_ui_specification.md`
**Out of scope:** `Reference/counselconnect_ui_spec.md` video-first layout and `Reference/videocallui_reference.png` (the image could not be read by the planning model; no image-derived requirements).

## Goal

Let the Student explicitly allow or decline video calls per appointment. Video is blocked unless the Student allows it, while text chat remains available. Rebuild the Student/Counselor scheduled-session screen as the chat layout in `Reference/chat_ui_specification.md` without exposing Counselor-private notes or unsupported controls as working features.

## Approved decisions

1. Permission is per appointment, stored server-side, and enforced by the call config and signaling authorization.
2. New and existing appointments default to `PENDING`. No backfill; video requires a new explicit Student decision.
3. The Student can change the decision until the safety deadline. Revoking during an active call ends the call within the existing 30-second server revalidation window.
4. The permission prompt is a non-blocking card on the scheduled-session page. Chat and joining stay available.
5. The chat specification is implemented now. The existing global `AppNavBar` is reused; no duplicate global header.
6. The existing `AppointmentCallPanel` is reused as an inline expandable section opened from the chat header video icon.
7. Unsupported spec controls are visible but disabled: audio call, attachments, image/document composer actions, and a Student "Session Reflection" area. The Counselor's private notepad remains real; shared files keep the existing completion gate.

## Contracts to preserve

| Invariant / user capability | Owning contract and code | Regression test |
|---|---|---|
| Explicit join is required before reading/sending chat | `docs/REAL_TIME_MESSAGING.md`; `useAppointmentChat`; `ScheduledSessionPage` | `frontend/tests/scheduled-chat.test.cjs` |
| Messages are durable, ordered, and catch up after reconnect | `docs/REAL_TIME_MESSAGING.md`; `useAppointmentChat` | `scheduled-chat.test.cjs` |
| Call authorization is participant-only, ONLINE-only, CONFIRMED-only, and windowed | `docs/AUDIO_VIDEO_CALLS.md`; `AppointmentsService.call_context`; `calls/router.py` | `backend/app/tests/integration/test_calls.py` |
| No call media, SDP/ICE, history, or call audit rows are persisted | `docs/AUDIO_VIDEO_CALLS.md`; `calls/realtime.py` | `test_calls.py` |
| Student session files are unavailable before `COMPLETED`; Counselor files work while `CONFIRMED`/`COMPLETED` | `docs/PRIVATE_CLINICAL_DOCUMENTS.md`, `docs/COUNSELING_SESSION_RECORDS.md`; `SessionRecordWorkspace`, `useSessionDocuments` | `backend/app/tests/integration/test_session_records.py`, `frontend/tests/session-records.test.cjs` |
| The Counselor notepad is never returned to or rendered for the Student | ADR-035; `SessionRecordWorkspace`; `useSessionRecord` | `session-records.test.cjs` plus a new chat-sidebar privacy test |
| Existing call cleanup on hang-up, peer leave, unmount, window end, and session invalidation | `useAppointmentCall.js` | `frontend/tests/appointment-call.test.cjs` |
| Role/ownership/CSRF/background-refresh behavior is unchanged | `CurrentUser`, `AppointmentsService._owned`, `apiClient` | Existing auth/appointment/API tests |

Compatible API methods/paths: existing appointment, session, message, call, record, and document endpoints are unchanged. The new endpoint is additive; `video_call_permission` is an additive session field.

Intentional behavior changes:
- A confirmed ONLINE appointment no longer allows calls until the Student selects `ALLOWED`.
- The current session-page "Session record" rail tab is replaced by a compact private-notepad card plus an "Open full session record" link. The full record page remains the place to edit the assessment and finalize.
- The session page gains the chat-spec layout; existing join/send/outcome/file behavior is retained under new markup.

## Backend changes

### 1. Migration

Add `backend/migrations/versions/20261026_appointment_video_call_permission.py`.

- `revision = "20261026_video_call_permission"`
- `down_revision = "20261025_session_records"` (the current head, already present as uncommitted work; do not revert it)
- Add to `appointments`:
  - `video_call_permission` `VARCHAR(16) NOT NULL DEFAULT 'PENDING'`
  - `video_call_permission_decided_at` `DATETIME(6) NULL`
  - `CHECK (video_call_permission IN ('PENDING','ALLOWED','DECLINED'))` as `chk_appointments_video_call_permission`
- No data backfill. Existing rows become `PENDING`.
- Downgrade drops the check constraint and both columns.
- Do not edit the baseline `db/CounselConnect_Initial_Database_v4.1.sql`.

### 2. Model and schemas

`backend/app/modules/appointments/models.py`:
- Add the two columns to `Appointment`.
- Add the check constraint to `Appointment.__table_args__`.

`backend/app/modules/appointments/schemas.py`:
- `VideoCallPermission = Literal["PENDING", "ALLOWED", "DECLINED"]`.
- Add `video_call_permission: VideoCallPermission` to `AppointmentSessionResponse`.
- Add `AppointmentVideoCallPermissionRequest` with `model_config = ConfigDict(extra="forbid")` and `permission: Literal["ALLOWED", "DECLINED"]`. `PENDING` is not accepted from clients.

### 3. Service authorization

`backend/app/modules/appointments/service.py`:
- Add `set_video_call_permission(self, actor, appointment_id, permission)`:
  - `authorize(actor)`.
  - Require `actor.role_code == "STUDENT"`; otherwise `403 FORBIDDEN_ROLE`.
  - Lock and resolve the owned appointment with `_locked_owned` so non-participants get the existing 404 behavior.
  - Require `status == "CONFIRMED"`, `appointment_mode == "ONLINE"`, and `utcnow() < slot.ends_at + chat_grace_minutes`; otherwise `409 VIDEO_CALL_PERMISSION_NOT_APPLICABLE`.
  - Set `video_call_permission` and `video_call_permission_decided_at = utcnow()`.
  - Do not create an audit event; calls remain outside call-history/audit persistence.
- In `session_response`, add `video_call_permission=appointment.video_call_permission` and change `can_call` to:
  `live_window and appointment.video_call_permission == "ALLOWED"`.
- In `call_context`, change `can_call` to the same condition.
- Leave `_live_window` unchanged so chat capabilities are unaffected.

### 4. Router

`backend/app/modules/appointments/router.py`:
- Add:
  `PUT /appointments/{appointment_id}/video-call-permission`
- Body: `AppointmentVideoCallPermissionRequest`.
- Response: `AppointmentSessionResponse`.
- Implementation:
  - Call the service method.
  - `_commit_and_publish(service, appointment)` so both participants receive `appointment_session_changed`.
  - Return `service.session_response(actor, appointment)`.
- The router already applies `Cache-Control: no-store` and CSRF/role dependencies.

### 5. Test harness and generated contract

- `backend/app/tests/conftest.py`: add the new migration file constant, loader, and `.upgrade()` call after `20261025_session_records`.
- Update `test_calls.py`'s `_appointment` helper to accept `video_call_permission="ALLOWED"` by default so existing call tests keep testing the call window. Add explicit PENDING/DECLINED cases.
- Regenerate `contracts/openapi.json` after the backend change.

## Frontend changes

### 1. Session hook

`frontend/src/features/messaging/useAppointmentChat.js`:
- Add `setVideoCallPermission(permission)`:
  - `PUT /appointments/${appointmentId}/video-call-permission` with `{ permission }`.
  - Replace the local `session` with the returned `AppointmentSessionResponse`.
  - Expose `busy`/`error` consistently with join/send.
- Listen for the existing global `appointment-updated` event; when `detail.appointment_id` matches, call `loadSession(true)` so both participants see permission changes immediately. The request already uses `X-Background-Refresh` and must not renew idle activity.
- Keep the 15-second background refresh as the fallback.

### 2. New session components

Create under `frontend/src/components/session/`:

- `SessionChatHeader.jsx`
  - Avatar circle with initials (no avatar URL exists), peer name, "In session" badge based on the peer join timestamp, connection status.
  - Static lock icon labelled "Private session".
  - Audio button disabled with title "Audio calls are not available yet."
  - Video button:
    - Enabled only when `video_call_permission === "ALLOWED"` and the session is a confirmed ONLINE appointment.
    - Disabled with an explicit title for `PENDING`, `DECLINED`, face-to-face, and non-confirmed states.
    - Toggles the inline call section.
  - Counselor outcome actions remain available under the existing conditions.
- `SessionMessageStream.jsx`
  - Scrolling message area with date pills (`TODAY, SEPT 16` style, `Asia/Manila`), incoming/outgoing bubbles, sender initials, and timestamps.
  - Use `message.sender_user_id === user.user_id` for direction and `message.message_id` for identity.
  - Keep sequence ordering from the hook; do not re-sort by display time.
  - Empty, not-joined, reconnecting, and closed states.
- `SessionComposer.jsx`
  - Pill-shaped input bar with disabled paperclip/image/document buttons and titles.
  - `textarea` with `maxLength=4000`, send button, disabled when `can_send` is false or the message is blank.
  - Preserve the existing submit/send path.
- `VideoPermissionCard.jsx`
  - Non-blocking card in the main column for confirmed ONLINE appointments before the safety deadline.
  - Student `PENDING`: "Video for this session?" with "Allow video calls" and "Continue with chat only".
  - Student `ALLOWED`: status plus "Switch to chat only"; warn that switching ends an open call.
  - Student `DECLINED`: status plus "Allow video calls".
  - Counselor `PENDING`: "Waiting for the student to allow video calls."
  - Counselor `DECLINED`: "The student chose chat only for this session."
  - Counselor `ALLOWED`: status only.
  - Show saving, error (`role="alert"`), and disabled states.
- `SessionSidebar.jsx`
  - Stacked sections in this order: notepad/reflection, shared files, session details, record link.
  - Counselor: `CounselorNotepadCard` with the real private notepad.
  - Student: disabled "My Session Reflection" placeholder; never render the Counselor's notepad content.
- `CounselorNotepadCard.jsx`
  - Use `useSessionRecord` and `recordToForm`.
  - Autosave through `queueSave` only when `record.can_edit`.
  - Show save status and "Open full session record" link to `#session-record/{appointment_id}`.
  - Do not also mount `SessionRecordWorkspace` on the session page; two editors would conflict.
- `SharedFilesPanel.jsx`
  - Use `useSessionDocuments(appointmentId, enabled)`.
  - Enabled: Counselor while `CONFIRMED`/`COMPLETED`; Student only while `COMPLETED`.
  - Upload (`+ Add Document`) only in those allowed states; preserve delete for `doc.can_delete` and download.
  - Show loading, error, empty, and the existing completion-gate message.
  - Use the real document list; no sample files.
- `SessionDetails.jsx`
  - Move the existing details rows into the sidebar; show both participants, campus, mode, schedule, and status.

### 3. Page orchestration

`frontend/src/pages/ScheduledSessionPage.jsx`:
- Keep the hash route `#session/{appointment_id}` and the appointment-detail fetch for names.
- Use the chat hook once and pass state down; do not duplicate `useAppointmentChat`, `useSessionRecord`, or `useSessionDocuments`.
- Layout: main chat card plus right sidebar, `lg:grid-cols-[minmax(0,1fr)_22rem]`, sidebar min width about 300px; stack on mobile.
- Render the permission card before the message stream for eligible appointments.
- Render `AppointmentCallPanel` inline above the message stream only when the call section is open and permission is `ALLOWED`; pass `can_call` from the session capabilities.
- Close the inline call section when permission stops being `ALLOWED` or the appointment stops being confirmed ONLINE.
- Preserve: lobby before start, explicit `Join scheduled session`, room-security behavior, counselor outcome buttons, closed-conversation message, student file/summary link, and the 1-second clock used for window state.
- Do not change `AppNavBar`; the existing global header satisfies the spec's global header. Do not add a second header.

### 4. Visual and accessibility details

- Use Tailwind with the spec tokens locally: `#2E7D32` primary, `#F8F9FA` page, `#FFFFFF` cards/bubbles, `#1F2937` text, `#6B7280` muted, `#E5E7EB` borders, 12–16px card radii, 24px/9999px composer radius.
- Use Font Awesome icons already loaded by the app; no emoji icons.
- Every icon-only control needs an accessible name; disabled controls need a title explaining why.
- Keep focus styles and keyboard operation. Do not rely on color alone for permission/connection state.
- `formatSchedule` remains for dates; add a small `Asia/Manila` message-time/day helper for chat timestamps.

### 5. Spec mapping and deliberate deviations

| Spec element | Implementation |
|---|---|
| Global header, nav, bell, avatar | Existing `AppNavBar`; not duplicated |
| Chat header avatar/name/online badge | Initials, peer name, "In session" from join timestamps |
| Security icon | Static lock labelled "Private session" |
| Audio icon | Disabled placeholder |
| Video icon | Permission-gated; opens inline call section |
| Message stream/date pill/bubbles/timestamps | Implemented |
| Pill input bar, attachments, send | Text/send implemented; attachment buttons disabled |
| Right-sidebar notepad | Real Counselor-only notepad; Student sees a disabled reflection placeholder |
| Shared files/+ Add Document | Real data with existing completion gate |
| Sample names/files/notes | Never hard-coded; use authorized appointment/document data |

## Tests

### Backend

Add to `backend/app/tests/integration/test_calls.py`:
- Appointment default `PENDING` blocks `can_call`, returns no ICE servers, and rejects the signaling socket.
- Student `ALLOWED` enables call config and signaling inside the window.
- Student `DECLINED` blocks both.
- Switching `ALLOWED` to `DECLINED` during a connected socket ends it with `CALL_UNAVAILABLE` under a shortened revalidation interval.
- Counselor cannot change permission (`403 FORBIDDEN_ROLE`); other Student/Counselor gets 404; staff/pending Student gets 403.
- Face-to-face, non-confirmed, and after-deadline requests return `409 VIDEO_CALL_PERMISSION_NOT_APPLICABLE`.
- Invalid values/unknown fields return 422.
- Existing call tests retain their window/participant/signaling assertions with the helper defaulting to `ALLOWED`.
- No call/media/audit rows are created by permission changes.

Add or update appointment/session tests to assert `video_call_permission` is present and `can_call` is false by default.

### Frontend

Update `frontend/tests/scheduled-chat.test.cjs`:
- Add `video_call_permission` to every session fixture.
- Keep the join/catch-up/send assertions under the new markup.
- For the call test, set `ALLOWED` and click the video header button before looking for "Join video call"; assert no media request on mount.

Add `frontend/tests/session-chat-ui.test.cjs`:
- Student PENDING permission card; allow sends the PUT and updates the UI; chat remains usable.
- Student DECLINED sends the PUT and leaves chat usable.
- Counselor PENDING/DECLINED sees the correct status and cannot start a call.
- `appointment-updated` refreshes the session on the other role's screen.
- Incoming/outgoing bubbles, date pill, and timestamps render.
- Disabled audio/attachment actions are labelled and disabled.
- Student sees the completion-gate message and no file request before `COMPLETED`; Counselor sees files while `CONFIRMED`.
- The Counselor notepad is editable; the Student tree never contains the notepad text.

Keep `frontend/tests/appointment-call.test.cjs` and `frontend/tests/session-records.test.cjs` passing without weakening assertions.

## Documentation

Update only the owning contracts and affected references:

- `docs/AUDIO_VIDEO_CALLS.md`: Student permission, default `PENDING`, endpoint, `can_call` semantics, revocation behavior, no media/audit persistence.
- `docs/API_CONTRACT.md`: new endpoint, request/response, session field, stable error code.
- `docs/APPOINTMENT_SCHEDULING.md`: online-session step, chat-only fallback, required permission tests.
- `docs/DATABASE.md`: new appointment columns, check constraint, migration.
- `docs/REAL_TIME_MESSAGING.md`: declining video does not affect text chat.
- `.ai/NAMING_CONVENTIONS.md`: add the approved video-call permission states.
- `.ai/DECISIONS.md`: add ADR-036 for per-appointment Student video consent; reference it from ADR-034.
- `.ai/CURRENT_TASK.md`: risk, scope, preserved contracts, verification, and completion status per the workflow.
- Regenerate `contracts/openapi.json`.

## Verification

Run the narrow checks first, then the broader suite:

```powershell
# Backend (requires COUNSELCONNECT_TEST_DATABASE_URL for counselconnect_test)
& ./backend/.venv/Scripts/python.exe -B -m pytest backend/app/tests/integration/test_calls.py backend/app/tests/integration/test_appointments.py -q
& ./backend/.venv/Scripts/python.exe -B -m pytest backend/app/tests -q

# Frontend
node --test frontend/tests/appointment-call.test.cjs frontend/tests/scheduled-chat.test.cjs frontend/tests/session-chat-ui.test.cjs
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build

# Migration and generated contract (run from backend/)
& ./.venv/Scripts/python.exe -B -m alembic heads
& ./.venv/Scripts/python.exe -B -m alembic upgrade head
& ./.venv/Scripts/python.exe -B -m alembic downgrade -1
& ./.venv/Scripts/python.exe -B -m alembic upgrade head
& ./.venv/Scripts/python.exe -B scripts/export_openapi.py --check
```

Run the migration upgrade/downgrade on a disposable schema only. If the test database URL is unavailable, record the skipped MySQL tests as a verification gap, not a pass.

Manual QA with two roles:
- Student sees the permission card; chat works while `PENDING`.
- Student allows; Counselor sees the change and can join video; chat remains available.
- Student switches to chat only; the active call ends within the revalidation window; Counselor sees chat-only state.
- Student declines; Counselor cannot call; chat still works.
- Face-to-face and non-confirmed appointments show no permission prompt and no call action.
- Student files remain blocked during `CONFIRMED`; Counselor files work; Student files work after `COMPLETED`.
- Counselor notepad is not visible to the Student.
- Camera/microphone denial shows the call error while chat remains usable.

## Risks and limitations

- The permission is a HIGH-risk authorization change. The server, not the hidden UI, must remain authoritative.
- Default `PENDING` changes existing behavior: previously confirmed online appointments lose video until the Student decides. This is intentional and must be documented.
- The Student can revoke during a call; the call ends on the next server revalidation (up to 30 seconds). The UI warning must state this.
- The chat redesign removes the rail record workspace. The full record link must remain visible so assessment/finalization access is not lost.
- The Counselor's notepad autosave must exist in exactly one component on the page to avoid conflicting writes.
- Unsupported spec controls are disabled placeholders, not implemented features; do not imply they work.
- The current worktree contains uncommitted session-record and call work. Preserve it; build the new migration on `20261025_session_records`.
- This task requires backend, migration, and docs changes. The standing frontend-only rule must not be applied blindly; if the team requires a frontend-only task, split this plan into a backend handoff and a frontend follow-up.

## Implementation order

1. Backend migration, model, schema, service, router.
2. Backend test-harness migration load and focused tests.
3. Frontend session hook and permission action.
4. New chat-spec components and page orchestration.
5. Frontend tests and selector updates.
6. Docs, ADR, OpenAPI regeneration.
7. Full verification and HIGH-risk review.
