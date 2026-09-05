# CounselConnect — Real-Time Messaging

## Contract

Each conversation is one authorized Student ↔ one authorized Counselor. Guidance Staff has no access. Validate participant scope and `conversation_type` on open, read, send, reconnect, and close; handle client message IDs to avoid duplicate sends where practical.

Approved conversation types are:

- `GENERAL`: ordinary authorized Live Chat independent of an appointment or SOS case.
- `APPOINTMENT`: dedicated to one confirmed online appointment.
- `SOS`: dedicated to one authorized SOS case.

A conversation must not be linked to both an appointment and SOS case. All participants require a valid approved session. Genuine send/read/navigation actions may renew the one-hour idle timer; WebSocket ping/pong, automatic reconnect, polling, and connection heartbeats do not.

## Appointment-linked conversations

- The appointments service supplies an authorized confirmed-online-appointment reference when the scheduled start is reached.
- Messaging revalidates the Student, Counselor, appointment mode/status, and participant match before creating or reopening the conversation.
- One appointment may link at most one `APPOINTMENT` conversation, and one conversation may belong to at most one appointment.
- Face-to-face, pending, rejected, cancelled, completed, or otherwise unauthorized appointments cannot create a new appointment conversation.
- Closing an appointment conversation reports session closure to the appointment workflow but does not by itself invent the appointment outcome.

Optional expression flow: local scan → session-only `observed_expression_cue` → Counselor read-only context. No raw camera data enters message/API payloads, and scan denial/failure never blocks chat.

## Lifecycle/retention

- Conversation: authorized open → text exchange → closed with `closed_at`.
- Retain message bodies for 30 days after closure, then delete bodies/rows according to implementation while keeping only permitted minimal conversation/audit metadata.
- Keep the expression cue only for the active interaction; discard on close.
- No audio/video recording, generated transcript, or automatic summary.
- Session expiry closes protected access but must not corrupt persisted messages or falsely mark an appointment/SOS outcome. After reauthentication, reconnect and reauthorize from server state.

## Required tests

- Participant/role authorization and cross-conversation denial.
- Conversation-type validation and prevention of appointment/SOS dual linkage.
- General Live Chat independent of appointment state.
- Confirmed online appointment access at the scheduled start.
- Denial before confirmation/start and after rejection/cancellation.
- Appointment/conversation Student and Counselor mismatch denial.
- Face-to-face appointment conversation denial and unique appointment link.
- Send/retry/idempotency, reconnect, and close behavior.
- Cue present/absent without raw media.
- Cleanup deadline and failure handling.
- One-hour idle and 12-hour absolute session expiry, five-minute continuation warning, revocation, reauthentication, and proof that heartbeat/reconnect traffic does not renew idle activity.

## Pending

Real-time transport, delivery/read semantics, maximum message size, attachment support (not assumed), exact retained metadata, and any approved pre-start join window.
