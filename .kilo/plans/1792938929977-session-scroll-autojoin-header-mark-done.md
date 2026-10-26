# Session UI: scrollable tabs, auto-join chat, header Mark as done

**Status:** READY FOR IMPLEMENTATION
**Risk:** HIGH for the completion action placement; MEDIUM for auto-join; LOW for layout. Run the HIGH-risk read-only review before acceptance.
**Scope:** `frontend/src/pages/ScheduledSessionPage.jsx`, `SessionRecordPage`, the shared session-record workspace/hooks, and owning docs.
**No backend/schema/API change.** No migration; no OpenAPI regeneration expected.

## Goal

1. On both the Student and Counselor scheduled-session page, the right-hand tab content (Chat, Details, and the Counselor's Session record/files) scrolls inside the panel; the page itself does not scroll on desktop. The separate `#session-record/{appointment_id}` page's tab content also scrolls.
2. At the scheduled start, the open session page joins automatically so chat/composer is usable without clicking **Join scheduled session**.
3. The Counselor's **Mark as done** button moves to the session header beside **Mark no-show**. The Record panel no longer shows it.

## Approved decisions

1. Student keeps the existing **Session files & summary** link to the separate record page; do not add a Files tab to the session page.
2. Auto-join uses the existing `POST /appointments/{appointment_id}/session/join` once when the page is open at/after the scheduled start. Server authorization, conversation creation, and join rows are unchanged. A retry control appears only if that request fails.
3. **Mark as done** is moved, not duplicated. It still saves the current notepad/assessment before calling `POST /mark-done` (preserve ADR-037 behavior). Removing the button from the Record panel does not change the endpoint, validation, or atomic finalize+complete step.
4. Desktop (`lg` and up): viewport-height layout; the left call column and right tab panel scroll independently. Mobile: normal page scroll, but the aside tab panel gets a bounded height and scrolls internally.
5. No new API, schema, permission, or Student file-visibility change.

## Preserved contracts

- Join authorization stays participant/`CONFIRMED`/`ONLINE`/window bound; the join request is still required and still records `student_joined_at`/`counselor_joined_at`.
- Chat join/send/catch-up, WebSocket reconnect, call panel, video permission, and appointment outcome behavior are unchanged.
- Mark as done remains save-first and atomic; missing/incomplete/pre-start errors are unchanged.
- Students never see the Counselor notepad or a `DRAFT` assessment; files stay gated by appointment status.
- `SessionRecordWorkspace` used by `SessionRecordPage` keeps **Finalize record** and **Reopen for editing**.

## Current state to account for

- `ScheduledSessionPage` renders the workspace only when the page tab is `record`; the record state lives inside `SessionRecordWorkspace`.
- The page has a 1-second clock (`tick`) used for window state.
- `useAppointmentChat.join()` returns nothing today; `can_join` stays true after joining because it only reflects the live window + open conversation, so auto-join must also check the participant's `*_joined_at`.
- The Student page does not fetch `/record`; keep it that way. Add an `enabled` gate to `useSessionRecord`.
- `scheduled-chat.test.cjs` currently clicks **Join scheduled session** and finds **Mark as done** inside the Record panel; both test shapes change.
- The separate chat-UI/video-permission plan is not implemented. If it lands first, re-apply auto-join/header placement to its header; this plan targets the current page.

## Implementation tasks

### 1. Lift the record editor to the page (enables the header action)

Files: `frontend/src/features/sessionRecords/useSessionRecord.js`, new `frontend/src/features/sessionRecords/useSessionRecordEditor.js`, `frontend/src/components/sessionRecords/SessionRecordWorkspace.jsx`.

- Add `enabled = true` to `useSessionRecord(appointmentId, enabled)`:
  - When disabled, do not call `load` and leave `loading` false. Keep the existing `save`/`action` functions.
- Create `useSessionRecordEditor(appointmentId, enabled)`:
  - Calls `useSessionRecord(appointmentId, enabled)`.
  - Owns `form` (`EMPTY_RECORD`), the `recordToForm` sync effect, `update`, `finalize`, `reopen`.
  - `markDone(onMarkDone)`: if `record?.can_edit`, `await save(dirty ? form : recordToForm(record))`; if the save fails return `null`; then `await onMarkDone()`; then `reload()`; return the result.
  - Track `dirty` (set by `update`, cleared by the record sync) so a header click immediately after load cannot save `EMPTY_RECORD` before the form-sync effect runs.
- Split `SessionRecordWorkspace`:
  - `SessionRecordWorkspace` takes an optional `editor`; if absent, an inner component calls `useSessionRecordEditor(appointment.appointment_id, true)`. Do not call the hook conditionally in the same component.
  - Render the existing UI as a presentational `SessionRecordView` using `editor.recordApi`, `editor.form`, `editor.update`, `editor.finalize`, `editor.reopen`.
  - Remove the `markDone`/`onMarkDone`/`markDoneDisabled` Mark as done branch from `RecordPanel`; keep **Finalize record** only when `variant !== "rail"` (standalone page), and **Reopen** as-is.
  - Keep the existing `missingFields` alert in the Record panel; the page passes `missingFields={chat.missingFields}` and switches to the Record tab on failure.
  - Keep `actionBusy` field locking.
- `ScheduledSessionPage` calls `useSessionRecordEditor(appointmentId, isCounselor)` once and passes `editor` into the workspace. Students get `enabled: false` (no `/record` request).

### 2. Move Mark as done to the header

File: `frontend/src/pages/ScheduledSessionPage.jsx`.

- Keep the header action group condition (`isCounselor && sessionStarted && session.status === "CONFIRMED"`).
- Render **Mark as done** first, then **Mark no-show**.
- Show Mark as done only when `editor.recordApi.record` is non-null (a successful GET; `record_id` may be null when no row exists yet). Disable it while `chat.busy`, `editor.recordApi.loading`, or `editor.recordApi.saving`.
- Handler:
  ```js
  const markSessionDone = async () => {
    const result = await editor.markDone(chat.markDone);
    if (!result) setTab("record");
  };
  ```
  Switching to the Record tab makes the existing `recordApi.error` / missing-field alert visible. Do not duplicate field-label mapping in the header.
- Remove the old Mark as done UI from the Record panel. Do not add a header **Mark completed** button.

### 3. Auto-join at the scheduled start

Files: `frontend/src/features/messaging/useAppointmentChat.js`, `frontend/src/pages/ScheduledSessionPage.jsx`.

- Make `join()` return `true` on success and `false` on failure (call sites that ignore the value are unaffected).
- In the page (before the `!chat.session` early return), add:
  - `joinFailed` state and an `autoJoinAttempted` ref.
  - `chatOpen = Date.now() >= new Date(session.messaging_opens_at).getTime()` (the existing 1-second tick re-renders this).
  - Effect: when `session` exists, `chatOpen`, `can_join`, the current role's `*_joined_at` is null, `!chat.busy`, and no attempt yet:
    - set `autoJoinAttempted.current = true`, clear `joinFailed`, call `chat.join()`, and set `joinFailed = !ok`.
  - Reset the ref and `joinFailed` when `appointmentId` changes.
  - The ref prevents a retry loop after a failed join; `can_join` alone is not enough because it stays true after joining.
- Replace the manual **Join scheduled session** button:
  - While `chatOpen && !participantJoined && chat.busy`: show `Joining the session…`.
  - If `joinFailed`: show the existing error plus a **Retry joining** button that calls `chat.join()` again (reset `joinFailed` on success).
  - Before start: keep the lobby copy.
  - After join: the composer appears through `can_send`; no extra click.
- If the page opens after the start, the same effect joins immediately.

### 4. Scrollable tab layout

Files: `frontend/src/pages/ScheduledSessionPage.jsx`, `frontend/src/components/sessionRecords/SessionRecordWorkspace.jsx`, `frontend/src/pages/SessionRecordPage.jsx`.

- Session page (`lg` and up):
  - `main`: `min-h-screen ... lg:h-[100dvh] lg:overflow-hidden`.
  - Inner wrapper: `lg:flex lg:h-full lg:flex-col`; grid: `lg:min-h-0 lg:flex-1`.
  - Left call column: `lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain`.
  - Aside: remove `h-fit`; use `flex min-h-0 flex-col` plus a mobile bound (`max-h-[75dvh]`) and `lg:max-h-full`.
  - Keep the tablist and the Student's files/summary link outside the scroll area.
  - Tab panel:
    - Chat: `flex min-h-0 flex-1 flex-col overflow-hidden`; `SessionChat` becomes a flex column with `min-h-0 flex-1`, the message list `min-h-0 flex-1 overflow-y-auto` (drop `max-h-[28rem]`), and the composer pinned at the bottom.
    - Details/Record: `min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1`.
- `SessionRecordWorkspace` gets a `scrollable` prop used only by `SessionRecordPage`:
  - When true, the section is a flex column; tablist fixed; the panel content `min-h-0 flex-1 overflow-y-auto`.
  - The rail (`scrollable` false) keeps the current flow; the outer session panel scrolls it.
- `SessionRecordPage`: viewport-height layout on `lg` (`lg:h-[100dvh] lg:overflow-hidden`), header fixed, card `lg:min-h-0 lg:flex-1`, and pass `scrollable` to the workspace. On mobile, bound the card (`max-h-[80dvh]`) so its tabs scroll rather than growing the page indefinitely.
- Accessibility basics: keep the tablist/tabpanel associations; add `tabIndex={0}` to the scrollable tab panel so keyboard users can scroll it.

### 5. Tests

File: `frontend/tests/scheduled-chat.test.cjs` (plus a check of `session-records.test.cjs`).

- Auto-join:
  - Rewrite the first test: mount, wait one tick, assert `POST /session/join` happened without a click, then edit/send the message.
  - Rewrite the counselor test the same way; add a `/record` mock because the page-level editor now loads it for Counselors.
  - Add a failure/retry test: `/session/join` returns 503 once, assert the error + **Retry joining**, then return 200 and assert the participant joins.
  - Update the call-panel test fixture to `can_join: false` (or mock join) so it does not auto-join.
- Mark as done:
  - Assert the header shows **Mark as done** and **Mark no-show**, and no **Mark completed**.
  - Open the Record tab, edit a field, click the header **Mark as done**: assert one `PUT /record` (current form) before `POST /mark-done`, then the completed state.
  - Already-`FINAL`: click the header action; assert no additional PUT.
  - Failed record load: header action is absent/disabled; the Record tab shows the load error.
  - Incomplete: click the header action, mock `409 RECORD_INCOMPLETE`, assert the page switches to the Record tab and names the missing field; the appointment stays `CONFIRMED` and the record `DRAFT`.
  - Assert the Record panel no longer renders **Mark as done**.
- `session-records.test.cjs`: keep the existing page-variant **Finalize record** / **Reopen for editing** tests green. Add one assertion that the rail variant does not show **Mark as done** (it is header-only on the session page).
- No DOM/CSS test for the scroll layout (presentation-only). Check the tabs still switch and their content renders.

### 6. Documentation / ADR

- `.ai/DECISIONS.md`: add **ADR-038** (ADR-036 is reserved for the video-permission plan; ADR-037 is in use):
  - Session page auto-submits the existing join request once at/after start; server authorization/join rows unchanged; retry on failure.
  - Mark as done moved to the header; save-first and the endpoint are unchanged.
  - Amend ADR-037's last line to say the control location moved to the header; annotate ADR-028's explicit-join clause with the session-page auto-submit.
- `docs/REAL_TIME_MESSAGING.md`: replace "first explicit authorized join" with the auto-submitted join wording; state that the request is still required.
- `docs/APPOINTMENT_SCHEDULING.md`: step 7, the Scheduled Live Chat/UI boundary, and the required-tests list; note auto-join, retry, and the header Mark as done.
- `docs/COUNSELING_SESSION_RECORDS.md`: Mark as done is in the session header; behavior and save-first unchanged.
- `docs/API_CONTRACT.md`: annotate the `POST /session/join` row that the session page submits it automatically at start; no endpoint/response change.
- `.ai/CURRENT_TASK.md`: record scope, preserved contracts, actual verification, and limitations at implementation time.
- Do not edit `docs/DATABASE.md`; no schema change. Do not regenerate OpenAPI unless an implementation step unexpectedly changes the API.

## Verification

```powershell
# Focused frontend
node --test frontend/tests/scheduled-chat.test.cjs frontend/tests/session-records.test.cjs

# Full frontend + build
npm --prefix frontend test
npm --prefix frontend run build

# Backend regression (no backend code changed)
# requires COUNSELCONNECT_TEST_DATABASE_URL; check for skips
pytest app/tests -q            # run from backend/
python -B scripts/export_openapi.py --check   # run from backend/
```

Manual QA:
- Student and Counselor open the session before start: lobby only; at start the join request runs automatically and the composer is usable without a click.
- Both sides: Chat/Details (and Counselor Record/Files) scroll inside the panel; the page does not scroll on desktop; mobile tab content is bounded.
- Join failure shows a retry; retry succeeds.
- Counselor: **Mark as done** sits beside **Mark no-show**; editing in the Record tab then clicking the header action saves first; incomplete fields switch to the Record tab and name the fields.
- `#session-record/{id}` tabs scroll while its tablist stays visible; Student still uses the separate files link and cannot see the notepad.

## Risks / notes

- Auto-join is a deliberate contract change from "user clicks Join" to "open page joins at start"; docs/ADR must match. It is still one authorized join request, not server-side auto-join on reads.
- The header completion action must keep the save-first sequence; do not let it call `/mark-done` directly while the form has unsaved edits.
- Moving the editor state to the page means the Counselor page fetches `/record` on mount. Students must stay gated off. The standalone record page keeps its own editor instance.
- If the future chat-UI/video-permission plan lands first, re-apply the header placement and auto-join to its new header/sidebar; the backend contract is unchanged.
- The desktop viewport layout uses `100dvh`; verify short laptop viewports and mobile browser chrome.
