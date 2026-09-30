# CounselConnect — Real-Time Messaging

## Contract

Each conversation is one authorized Student and one authorized Counselor. Revalidate participant ownership and conversation purpose on open, read, send, reconnect, and close. Other Counselors, Superadmin, and legacy Guidance Staff have no participant access.

Conversation types remain GENERAL, APPOINTMENT, and SOS. A conversation cannot be linked to both an appointment and an SOS case. GENERAL chat remains an unimplemented/future workflow unless separately approved; scheduled APPOINTMENT text chat is implemented.

## Scheduled appointment chat

- Confirmation does not create a conversation.
- The launcher/lobby appears 30 minutes before a confirmed ONLINE appointment.
- At or after start, the first explicit authorized join locks/revalidates the appointment and lazily creates/reuses its single APPOINTMENT conversation.
- REST is the durable source for ordered messages/history. FastAPI WebSockets deliver committed events; reconnect catches up through REST.
- The safety deadline is appointment end plus the configured 15-minute grace period.
- Timeout closes chat without inventing COMPLETED or NO_SHOW; the assigned Counselor records the outcome.
- Face-to-face, pending, rejected, cancelled, completed, unauthorized, or mismatched appointments cannot create a scheduled chat.

## Audio/video relationship

Planned WebRTC audio/video uses the same appointment participants/window but is a separate media/signaling domain described in AUDIO_VIDEO_CALLS.md. Text messages remain durable. Call media, recordings, transcripts, and automatic summaries are never message content or persistent records.

## Counseling-record relationship

Counselor draft notes and finalized assessments are not chat messages. Store them only through COUNSELING_SESSION_RECORDS.md authorization and lifecycle. Ending chat may signal that a session ended, but only the Counselor records appointment outcome and finalizes assessment.

## Retention and sessions

Message bodies are retained for 30 days after conversation closure under the current decision, then purged while allowed minimal metadata remains. Genuine send/read/navigation may renew the one-hour idle timer; WebSocket ping/pong, reconnect, polling, and heartbeats do not. Reauthentication must reauthorize from server state.

## AI boundary

Optional AI-assisted observation is consented/session-only and separate from messaging. No raw media, observed-cue history, or AI diagnosis enters message/API payloads or SOS logic.

## Required tests

Participant and multi-Counselor isolation; Superadmin/legacy-role denial; purpose validation; pre-window/unconfirmed/cancelled/face-to-face denial; participant mismatch; unique appointment link; send/retry/idempotency; reconnect/catch-up; timeout/outcome separation; message purge; session expiry; no heartbeat renewal; no clinical notes/media/AI observations in messages.

The process-local WebSocket registry supports one backend process in v1. Messages are text-only with a configurable 4,000-character default. Attachments, delivery/read receipts, and multi-process fan-out are not implemented.
