# Scheduled Live Chat implementation plan

Date: 2026-09-16. Status: implementation proposal; no application changes made.

## 1. Authoritative scope

Implement the supplied scheduled online counseling flow with the second supplied document taking precedence wherever they differ. Build appointment-linked, text-only chat for the owning Student and assigned Counselor. Guidance Staff has no access.

Exclude General Chat, SOS changes, expression processing, attachments, typing indicators, read receipts, voice/video, email/SMS, a general notification subsystem, Redis/Celery, multi-worker scaling, and a new routing library.

Existing booking, slot reservation, campus/location snapshots, authentication, and other conversation types must continue working. Store/API times are UTC; display Asia/Manila.

## 2. Repository findings

- `backend/app/modules/messaging/router.py` has no endpoints. Its service only validates and closes an already-linked appointment conversation. Frontend messaging is a placeholder.
- `appointments.conversation_id` is already nullable and unique. This prevents two appointments sharing one conversation, but alone does not prevent concurrent creation of two conversation rows for one appointment.
- Messages already have a nullable `client_message_id` and a unique `(conversation_id, client_message_id)` constraint. Sequence numbers, entry timestamps, and closure reasons are absent.
- Appointment confirmation currently creates no conversation: preserve that behavior.
- Appointment rescheduling rejects every existing conversation link. Replace this with the requested activity-based restriction.
- ADR-021 already approves the Student 24-hour cutoff, but the inspected cancellation/rescheduling service does not enforce it. Include enforcement and boundary tests.
- The database dependency commits after yielding. New message/join/outcome delivery needs an explicit successful commit before acknowledgment or broadcast.
- PyMySQL/SQLAlchemy operations are synchronous. WebSocket database work needs short-lived sessions created and closed inside thread-offloaded operations.
- The application already owns a COR cleanup worker through its lifespan. Reuse that lifecycle pattern for separate messaging maintenance without changing COR behavior.
- The MySQL test harness explicitly loads migrations; registering the new migration is required. Existing project notes report database tests skipped without the test database setting.
- The two plan files listed in the IDE were not present on disk when inspected. This document is the implementation plan.

## 3. Lifecycle and access rules

Let T be scheduled start, E scheduled end, and G a configurable grace period defaulting to 15 minutes. Use server time for every decision.

| State/time | Student experience | Backend behavior |
|---|---|---|
| Pending, rejected, cancelled, or face-to-face | No available scheduled chat | Deny join, history, send, and chat socket |
| Confirmed online, before T−30 | Disabled launcher with schedule/countdown | Metadata only; no conversation creation |
| T−30 ≤ now < T | Enabled launcher opens readiness lobby | Generic reminder; no messages, active entry, conversation row, or conversation socket |
| T ≤ now < E+G, not closed | Join and exchange text | First authorized join creates/returns one conversation and records actual entry |
| Counselor chooses COMPLETED or NO_SHOW | Student chat ends | Atomically record outcome, close conversation, and audit |
| now ≥ E+G without outcome | Chat locked; Counselor sees outcome needed | Close existing conversation with timeout reason; leave appointment CONFIRMED |
| Closed conversation | Student cannot read; assigned Counselor read-only | No reopening or sending; retained history only until purge |

Late joining remains possible until the safety deadline; remove the start+15-minute join cutoff. Leaving the page never changes the appointment outcome. Lobby access and reminder delivery never count as attendance. A join is evidence of entry, not proof counseling occurred.

If nobody joined by the deadline, do not create a conversation merely to close it. Derive the locked/outcome-needed state from the appointment schedule. Timeout processing must also run when the worker was unavailable; every join/send rechecks the deadline. Preserve the first closure time when the Counselor later records an outcome, so retention does not restart.

Proposed clarification: apply Counselor-only read access to all closed appointment conversations, including timeout/cancellation closures. Deny Student history after closure consistently. Record this explicitly in the feature contract.

## 4. Phase 1 — Reconcile contracts and decisions

Add ADR-028 with the supplied substance: appointment-derived launcher, T−30 lobby/reminder, lazy creation at T, Counselor closure, E+G safety lock without inferred outcome, and in-app/browser reminders only.

Update only affected clauses of ADR-018, ADR-021, and ADR-022; preserve the existing booking horizon, manual no-show rules, transport choice, and unrelated policies. Update ADR-008 to describe configurable prototype retention defaulting to 30 days, with institutional confirmation required before production.

Align `docs/REAL_TIME_MESSAGING.md`, `docs/APPOINTMENT_SCHEDULING.md`, `docs/API_CONTRACT.md`, `docs/DATABASE.md`, and directly affected requirement references. Document the cursor-list exception to normal page-number pagination. Distinguish requirements from implemented behavior until each phase lands. Record execution progress in `.ai/CURRENT_TASK.md` without erasing unrelated review findings.

## 5. Phase 2 — Additive schema and migration

Proposed fields:

| Table | Additions |
|---|---|
| appointments | Nullable `student_reminder_dispatched_at`, `counselor_reminder_dispatched_at` |
| conversations | Nullable unique FK `appointment_id`; nullable `student_joined_at`, `counselor_joined_at`, `closure_reason`; nonnegative `last_sequence_number` default 0 |
| messages | `sequence_number`, unique with `conversation_id` |

Keep the existing `appointments.conversation_id` for compatibility. The new unique `conversations.appointment_id` is the direct database backstop against multiple conversations for one appointment. Both links must be set atomically; document this deliberately redundant relationship. Use restrictive FK deletion behavior and explicitly unlink before deleting an unused conversation. GENERAL/SOS rows retain null appointment IDs.

Migration order: add nullable columns; validate existing links/type/participants and stop with a metadata-only diagnostic on inconsistent data; backfill appointment IDs; assign per-conversation sequences ordered by `(sent_at, message_id)`; initialize counters; then add indexes/constraints and sequence non-nullability. Preserve legacy null client IDs; require IDs on new appointment-message requests rather than globally breaking existing types.

Backfill activity conservatively: messages prove activity, but missing historical join timestamps do not prove a conversation unused. Do not allow deletion of ambiguous legacy links without establishing their provenance. Do not fabricate attendance.

Document closure reasons such as `COUNSELOR_OUTCOME`, `APPOINTMENT_CANCELLED`, and `TIMEOUT` before using them. They are metadata, not new appointment or conversation statuses.

Register the migration in `backend/app/tests/conftest.py`. Test upgrade with populated GENERAL, SOS, and APPOINTMENT records, including equal message timestamps. MySQL DDL is not assumed transactionally reversible; validate before enforcing constraints and document recovery from partial migration failure.

## 6. Phase 3 — Appointment lifecycle and REST services

Centralize capability calculation and authorization in services so REST, sockets, and workers use the same rules. Return server time, schedule, lobby/messaging/deadline timestamps, nullable conversation ID, role-specific capabilities, and safe reason codes. Metadata retrieval must never create or join a conversation.

Proposed routes, under `/api/v1`:

| Route | Purpose |
|---|---|
| `GET /appointments/{appointment_id}/session` | Authorized metadata, capabilities, and lobby state |
| `POST /appointments/{appointment_id}/session/join` | CSRF-protected, idempotent active join at/after T |
| `GET /conversations/{conversation_id}` | Authorized conversation metadata/capabilities |
| `GET /conversations/{conversation_id}/messages?before_sequence=250&limit=50` | Older history |
| `GET /conversations/{conversation_id}/messages?after_sequence=250&limit=50` | Missed messages in ascending order |
| `POST /conversations/{conversation_id}/messages` | Durable, idempotent text send; WebSocket distributes committed result |
| Existing appointment complete/no-show/cancel routes | Atomic appointment transition and linked conversation closure |

Use REST for outgoing messages to reuse existing cookie/CSRF protection; native WebSocket delivers new messages and lifecycle events. This satisfies the requested REST/WebSocket split without two competing send implementations. Document this transport choice explicitly.

History uses `{items, next_before_sequence, next_after_sequence, has_more}` with documented direction semantics; disallow simultaneous before/after cursors, bound `limit`, and default initial loading to the latest page. Return `no-store`. Proposed initial text limit: 4,000 characters, with a separate bounded request/frame byte limit. Reject blank/oversized text and render it as plain text.

Join transaction: authorize account and participant; acquire the established participant locks in ascending order, then appointment/slot/conversation locks in one documented order; re-read status/mode/schedule; return existing open conversation or create/link exactly one; set only the joining participant's first-entry time; audit minimal metadata; commit; then return/broadcast. A unique-conflict retry re-reads committed state and reauthorizes. Never reopen a closed conversation.

Send transaction: reauthorize current session, participant, type/link, appointment, conversation status, entry, and deadline; lock the conversation; find `client_message_id`; return the existing result only for the same sender and exact body; otherwise return an idempotency conflict. Allocate the next sequence under lock, insert, commit, then acknowledge/broadcast. No acknowledgment or event is emitted on commit failure. A previously committed retry may be acknowledged without creating a new message; it must not bypass current read authorization.

Generate client IDs once per logical send and reuse on retry; never put bodies or credentials in URLs/logs. No durable browser message cache in v1.

Scheduling integration:

- Enforce Student cancellation/reschedule at least 24 hours before the original start; exactly 24 hours is allowed. Counselor has no 24-hour restriction.
- Block reschedule or mode conversion after either participant enters the active conversation or any message exists. Lobby visits do not block changes.
- Preserve rescheduling to PENDING and existing replacement-slot/location validation. Permit mode-only changes through the same reschedule workflow with explicit same-slot validation, preserving the reservation and requiring review again; document this extension because the current implementation rejects same-slot requests.
- Before activity, reset both reminder timestamps on a successful schedule/mode/assignee change. Delete/unlink only a provably unused conversation in the same locked transaction.
- Serialize join versus reschedule/delete/cancel so no orphan conversation, stale participant access, or lost reservation is possible.
- Complete/no-show closes and updates atomically. Cancellation removes access and closes existing chat. Publish session-change events only after commit.

## 7. Phase 4 — Authenticated WebSocket delivery

Add `WS /api/v1/conversations/{conversation_id}/ws` and an appointment-reminder-only authenticated connection at `WS /api/v1/appointments/session-events`. The latter carries generic reminders/schedule invalidations, never chat content, and may exist before T. No conversation WebSocket opens in the lobby.

Implement a WebSocket-specific authentication adapter using the existing HttpOnly session cookie and session service. Validate an explicit Origin allowlist (CORS middleware alone is insufficient), active account, current session, ownership, and capabilities before admitting a connection. No credential query parameters. Revalidate during socket lifetime and before protected delivery; terminate expired/revoked sessions, including silent clients through a bounded periodic check. Session checks never extend activity.

Genuine REST actions may renew idle activity; background history catch-up, automatic joins/reconnects, metadata polling, sockets, and heartbeats must not. Preserve the one-hour idle/12-hour absolute timeout and existing continuation warning. Use the project's background-request convention consistently.

Keep an in-memory, single-process registry with bounded per-connection queues, multiple-tab support, backpressure, and cleanup on disconnect/logout. Offload each complete synchronous DB unit to a worker thread; do not share Session objects across threads or hold a session for a socket's lifetime.

Events include committed `message_created`, `session_closed`, and `appointment_session_changed`. Deliver only to currently authorized participants. REST remains authoritative after lost events. Reconnect by subscribing/buffering events, fetching all messages after the last contiguous sequence through a captured high-water mark, then merging/deduplicating buffered events. Repeat on gaps; do not advance the contiguous cursor over missing messages. A lost broadcast after commit is repaired by catch-up, not a second insert.

Enable `ws: true` in the Vite `/api` proxy and document production WebSocket upgrade support and the one-process deployment limit.

## 8. Phase 5 — Reminders, timeout, and retention maintenance

Add bounded, retryable appointment/messaging maintenance under FastAPI lifespan, with startup catch-up and clean shutdown. Reuse the COR worker pattern, not its domain service. Use injected clocks and short transactions for tests.

Reminder worker: select confirmed online appointments where T−30 ≤ now < T, recheck schedule/assignment under lock, and dispatch separately to the two participants. Set only the recipient timestamp successfully dispatched to an authenticated active connection; retry undispatched recipients. Do not send obsolete reminders after T or after cancellation/mode change. An appointment confirmed during the reminder window becomes immediately eligible.

Dispatch is best-effort and at-least-once: without a general notification outbox, a crash between delivery and timestamp commit can repeat an alert. Deduplicate by appointment, scheduled start, and recipient on the client; do not claim exactly-once delivery or that a dispatch timestamp proves the user saw it. After rescheduling, revalidate queued events against the current schedule. In-app alert is primary; browser notification is generic and only when permission and an active browser connection exist. Request permission from an explicit user gesture. No names, message bodies, or counseling details in browser notifications. Fully closed-app delivery is not guaranteed.

Timeout worker: close due open conversations using the same locks as sends/outcomes, record timeout reason, leave appointment CONFIRMED, and notify connected clients after commit. Derive the Counselor's outstanding outcome prompt even when no conversation exists. Requests enforce the deadline independently of worker timing.

Retention worker: permanently delete message rows in bounded transactions at `closed_at + configured retention`, default 30 days, and set `messages_purged_at` only after successful deletion. Retain minimal conversation/audit metadata; no transcript or summary. Deleting rows avoids retaining body fingerprints or unnecessary sender records. Never extend retention through repeated closure calls. Test retries and ensure due content is unavailable through the API even if deletion is temporarily delayed. Document backup expiry and mandatory purge replay before restored data is served. Production retention requires Guidance Office/Counselor and DPO confirmation.

## 9. Phase 6 — Frontend scheduled-session experience

Implement messaging service/hooks/components under `frontend/src/features/messaging`, a session page, and an appointment-derived launcher integrated with `App.jsx` and existing hash navigation. Preserve all appointment records and IDs; select the nearest eligible confirmed online appointment deterministically and allow other sessions through their appointment records. Do not turn the launcher into a general inbox.

- Disabled launcher before T−30; readiness lobby until T; active join at T only while the user is on the session screen.
- Use server capabilities and server/client clock offset for countdowns; refresh on focus and schedule changes without renewing authentication.
- Show Counselor session entry from appointment records; actual entry is distinct from reminder/lobby access.
- Plain-text message history with older-page loading and sending/sent/failed states. “Sent” means committed to MySQL, not read by the recipient.
- Show reconnect/catch-up status, stable client IDs on retry, and duplicate/gap reconciliation across acknowledgment and WebSocket events.
- Counselor end-session control confirms COMPLETED or NO_SHOW through existing outcome routes. Student window close only navigates away.
- Timeout locks sending for both participants and keeps the Counselor outcome prompt available. Assigned Counselor can view retained closed history read-only.
- Handle chat-specific 403/closed/unavailable errors locally; only session-authentication failure invokes global sign-in handling. Clear private state and sockets on logout, identity change, or loss of access.
- Keep existing SOS entry separate and unchanged. Remove “Live Chat not implemented” copy only once the integrated feature is working.

## 10. Verification and delivery gates

Implement in dependency order: contracts → migration → REST lifecycle/appointment guards → sockets → maintenance → frontend → integration verification. Each change includes focused tests; do not defer authorization tests until the end.

| Area | Required evidence |
|---|---|
| Time boundaries | Just before/exactly at T−30, T, E+G; configurable grace; late join; clock skew; Manila display |
| Access | Owning Student/assigned Counselor only; Guidance Staff/other users denied; pending/face-to-face/terminal denial; expired/revoked sessions; post-close Student denial and Counselor read-only |
| Concurrency | Simultaneous joins create one row; join versus unused deletion/reschedule/cancel; send versus close/timeout; unique ordered sequences under concurrent sends |
| Durability | Same-ID safe retry, different body/sender conflict, commit failure emits nothing, crash/lost broadcast repaired by REST catch-up |
| Scheduling | Student 24-hour boundary, Counselor exemption, entry/message activity blocks changes, lobby does not, mode-only validation, reset reminders, failed replacement preserves reservation |
| Reminders | Independent recipient retry, offline recipient, startup in window, cancellation/reschedule invalidation, browser denial, duplicate delivery, no idle renewal |
| Retention | Exact due time, timeout closure, late outcome preserves closure time, retry after failure, permanent body deletion, restored-backup procedure |
| Frontend | Launcher/lobby/chat states through mocked API boundary, history completeness/order, reconnect race, local 403 handling, logout cleanup, Counselor closure |
| Regression | Existing appointments, GENERAL/SOS rows, authentication, COR cleanup, and location snapshots preserved |

Run focused backend tests and then affected regression suites; all frontend tests (`npm test`) and production build (`npm run build`); OpenAPI export/snapshot verification using `backend/scripts/export_openapi.py`; `git diff --check`. Test WebSocket protocol separately because it is not described by OpenAPI.

Run real MySQL 8.4 integration tests with `COUNSELCONNECT_TEST_DATABASE_URL` pointing to the isolated test server/schema convention. Concurrency tests require separate connections and real committed fixtures, not the existing single outer-transaction fixture. Prove durability from a fresh connection. Skipped database cases do not satisfy readiness.

Perform a two-browser Student/Counselor walkthrough: confirm without a conversation, enter lobby without messages, join at T, exchange text, disconnect/reconnect, record an outcome, and exercise timeout with a controlled test clock. Verify generic browser notifications and no confidential content in URLs/logs/browser persistence.

Release only after migration, MySQL race tests, auth tests, and end-to-end flow pass. Deploy as one backend process; on rollback disable chat access/workers before reverting application code and preserve stored data rather than destructively downgrading message fields.

## 11. Explicit limitations and proposed defaults

The text length limit, same-slot mode-change behavior, and all-closure Counselor-only history rule above are concrete implementation proposals to document during Phase 1. The supplied timing, cutoff, reminder, privacy, and no-inferred-outcome rules are requirements, not open questions. Prototype notifications are best-effort and need an active application connection. Production retention and backup policy still need institutional confirmation. No runtime or database tests were run for this planning-only change.
