# CounselConnect — AI-Assisted Multimodal Session Observation

**Status: implemented for the optional session-long local expression cue (ADR-039).**

This optional feature supports, but never replaces, the Counselor's professional assessment during an online counseling session.

## Current input

- Local facial-expression observations from the active call, started by the Counselor and allowed by the Student for the session
- Voluntary Student self-report/check-in, appointment concern, and within-session trends remain planned and are not implemented

Voice/prosody analysis is excluded and remains pending.

## Local expression cue

- The Counselor sends a `request` over the existing appointment call WebSocket; the Student sees **Allow for this session** / **Decline**. Nothing scans until the Student allows that session.
- The Student's browser loads `@vladmandic/face-api` (TinyFaceDetector + FaceExpressionNet) lazily and analyzes its own call camera locally. About ten frames are averaged (~3 seconds), then the browser waits about two seconds and repeats until stopped. Only the current label and rounded confidence cross the WebSocket, and only to the other participant.
- Labels: `neutral`, `happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`.
- A cue is shared only when at least three samples exist and the top averaged label reaches `0.60`; otherwise the Student sends `unavailable`, the current cue clears, and no guess is displayed.
- Either participant can `stop`. On the Student's device, tab hiding aborts the live cue; call end, local stop, and unmount also abort it. Nothing is persisted, replayed, or reused for a later session.
- The Counselor sees the current label/confidence. The Student sees only the live-sharing status and Stop sharing, not the result. There is no history, trend, or automatic start.

## Output

The Counselor may see the shared observable cue with model confidence, such as “Neutral (72% confidence).” The system must not output diagnoses or clinical claims such as “the Student is depressed,” “has anxiety,” or needs medication.

## Safety and privacy

- Counselor-started and Student-consented per session
- Session-only; no AI observation history
- No raw audio/video, screenshots, facial images, landmarks, embeddings, transcripts, or recordings
- No identity recognition
- No influence on SOS urgency or access decisions
- Graceful skip when the model, camera, or face is unavailable
- Model confidence is not diagnostic accuracy
- Only the Counselor's independently authored assessment becomes durable

The UI labels observations as optional decision support and lets the Counselor ignore them.
