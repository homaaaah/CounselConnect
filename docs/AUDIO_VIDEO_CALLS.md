# CounselConnect — Scheduled Audio/Video Calls

**Status: implemented (ADR-034).**

## Contract

- One-to-one WebRTC call for the owning Student and assigned Counselor of a confirmed ONLINE appointment.
- The scheduled lobby opens 30 minutes before start; joining follows the appointment session window and server authorization. Calls open at the scheduled start and close at appointment end plus the configured 15-minute grace (`safety_deadline_at`).
- FastAPI provides authenticated signaling and session authorization over a dedicated appointment WebSocket. Media travels peer to peer; TURN/STUN configuration is environment based (`COUNSELCONNECT_CALL_ICE_SERVERS`).
- Signaling is ephemeral and single-process in v1: the server relays SDP/ICE and optional facial-observation events only, never records media, transcripts, candidates, observation history, IP addresses, or call history, and keeps no call table or audit events.
- A call does not create or join the appointment conversation and never changes the appointment outcome. Text chat remains a separate durable channel.
- Only the Counselor may end the counseling session and record the outcome; hanging up or disconnecting does not invent an outcome.

## Implementation

- `GET /appointments/{appointment_id}/call` returns the participant roles, window, and (only inside the window) the ICE server list. Responses are `no-store`.
- `WS /appointments/{appointment_id}/call/ws` authenticates the session cookie, requires an allowlisted Origin, authorizes the participant/status/mode/time on connect, and revalidates every 30 seconds by wall clock without renewing idle activity.
- The second participant to become ready is the offerer. The server relays `offer`, `answer`, and `ice-candidate` messages only to the other participant; unknown or oversized messages close with `1008`. A third user is rejected at authorization. A duplicate connection for the same participant replaces the older socket and ends the paired call for both; participants can rejoin.
- Optional `facial-observation` v1 messages start a temporary local observation: the Counselor sends `request`/`finish`, the Student sends `consent`/`decline`/`observation`, and either may send `stop`. Each observation slot carries request id, sequence, elapsed milliseconds, validity, allowlisted movement flags, and a bounded unavailable reason. The server validates the schema, roles, movement/reason allowlists, size/rate, and an in-memory active-consent cycle; it drops stale or out-of-consent observations and relays only to the other participant. Observation events are ephemeral: no storage, audit, logging, or history.
- Hang-up, peer departure, appointment cancellation/outcome, window end, and session invalidation end the call. Clients stop every track and close the peer connection; both participants must explicitly rejoin after a drop.
- TURN credentials are static environment configuration in v1; ephemeral coturn-issued credentials and multi-process signaling remain follow-ups. Media is not persisted.

## Privacy

- No call recording, server media storage, transcript, automatic summary, screenshots, or derived audio/video artifact.
- Never place media identifiers, concern text, or clinical details in generic notifications.
- Reauthorize appointment, participant, status, mode, and time on join/reconnect.
- Call signals contain network address candidates; do not log them or expose them outside the authorized participant pair.
- The optional facial observation runs locally/session-only under ADR-040, is consented per session, and does not change media retention. Only bounded movement/quality slots are relayed over the call WebSocket; the Student sees status only and the Counselor sees the temporary timeline/summary.

## Required tests

Unauthorized participant, wrong Counselor, face-to-face appointment, pre-window join, expired session, reconnect/rejoin, signaling isolation, end-session behavior, media-device denial, TURN failure fallback, invalid/oversized signals, duplicate connections, facial-observation role/schema/consent validation, stale-drop, timeline/summary, and stop, and proof that no media/recording/call record/observation history is persisted. Tests live in `backend/app/tests/integration/test_calls.py`, `frontend/tests/appointment-call.test.cjs`, and `frontend/tests/facial-observation.test.cjs`.
