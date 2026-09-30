# CounselConnect — AI-Assisted Multimodal Session Observation

**Status: approved target; planned implementation.**

This optional feature supports, but never replaces, the Counselor's professional assessment during an online counseling session.

## Initial inputs

- Local facial-expression observations from the active call
- Voluntary Student self-report/check-in
- Non-clinical context such as appointment concern and within-session trends

Voice/prosody analysis is excluded initially and remains pending.

## Output

The Counselor may see observable cues with model confidence, such as “sustained low-energy facial cue” or “self-reported distress increased.” The system must not output diagnoses or clinical claims such as “the Student is depressed,” “has anxiety,” or needs medication.

## Safety and privacy

- Counselor-triggered and Student-consented per session
- Session-only; no AI observation history
- No raw audio/video, screenshots, facial images, embeddings, transcripts, or recordings
- No identity recognition
- No influence on SOS urgency or access decisions
- Graceful skip when unavailable
- Model confidence is not diagnostic accuracy
- Only the Counselor's independently authored assessment becomes durable

The UI labels observations as optional decision support and lets the Counselor ignore them.
