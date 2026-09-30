# CounselConnect — Scheduled Audio/Video Calls

**Status: approved target; planned implementation.**

## Contract

- One-to-one WebRTC call for the owning Student and assigned Counselor of a confirmed ONLINE appointment.
- The scheduled lobby opens 30 minutes before start; joining follows the appointment session window and server authorization.
- FastAPI provides authenticated signaling and session authorization. Media travels peer to peer when possible; TURN/STUN configuration is environment based.
- Text chat remains available as a separate durable channel during the scheduled session.
- Only the Counselor may end the counseling session and record the outcome; disconnect alone does not invent an outcome.

## Privacy

- No call recording, server media storage, transcript, automatic summary, screenshots, or derived audio/video artifact.
- Never place media identifiers, concern text, or clinical details in generic notifications.
- Reauthorize appointment, participant, status, mode, and time on join/reconnect.
- AI observation, if separately consented, runs locally/session-only under ADR-035 and does not change media retention.

## Required tests

Unauthorized participant, wrong Counselor, face-to-face appointment, pre-window join, expired session, reconnect, signaling isolation, end-session behavior, media-device denial, TURN failure fallback, and proof that no media/recording is persisted.
