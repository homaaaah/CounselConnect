# CounselConnect — AI-Assisted Facial Observation

**Status: implemented prototype (ADR-040).** The historical filename is retained to preserve links. This feature observes selected visible movements; it does not measure emotion, diagnose, or assess.

## Goal and consent

The assigned Counselor may request optional facial observations during an authorized online appointment. The Student sees what is detected, who sees results, the temporary retention, and how to stop, then chooses **Allow for this session** or **Decline**. Consent is per request/session and is never stored. Ordinary counseling remains available either way.

The Student device runs the detector locally. The Student sees status and Stop controls, not results. The Counselor sees the temporary timeline and summary.

## Current implementation

- **Detector:** MediaPipe Face Landmarker blendshapes, loaded lazily from same-origin assets in `frontend/public/mediapipe/`. No cloud inference.
- **Enabled movements:** `smile`, `brow_raise`, and `brow_furrow`, enabled at client request on 2026-10-30. Thresholds remain provisional, unvalidated, and versioned in `observation.js`; do not claim accuracy until real-device validation passes.
- **Cadence:** about one analysis slot per second, no overlapping jobs. Busy, missing face, multiple faces, camera-off, low-quality, and model-failure slots are unavailable, never a movement or neutral label.
- **Transport:** bounded `facial-observation` v1 slots over the existing appointment call WebSocket. Only request id, sequence, elapsed time, validity, movement flags, and an allowlisted unavailable reason are relayed. The server enforces roles and an in-memory active-consent cycle; stale or out-of-consent observations are dropped. Nothing is logged, persisted, or audited.
- **Counselor view:** current supported movement, usable coverage, a bounded in-memory timeline, and a deterministic **Sentence / Bullets** summary. The summary is frozen for up to five minutes after **Finish observations and review**, and clears on expiry, withdrawal, navigation, refresh, logout, authorization loss, tab hiding, disconnect, call end, or completion.
- **Student view:** sharing status, tracking status, and Stop sharing. The Student never sees the movement results or summary.

## Calculation rules

- Coverage = 100 × valid samples / expected scheduled samples.
- Movement frequency = 100 × positive valid samples / valid samples.
- A predominant movement is shown only with at least 30 valid samples and 50% coverage.
- Percentages are one decimal place; counts stay integer. Movements can overlap.
- Zero data, insufficient coverage, ties, no supported movement, and truncation use explicit wording.
- “Not detected” does not mean neutral. “Unable to observe” is not a movement.

## Privacy and safety

- Optional, Counselor-started, Student-consented, local-device only, session-only.
- No screenshots, frames, landmarks, embeddings, recordings, transcripts, observation history, browser storage, analytics, or third-party inference.
- No automatic insertion into the clinical record; the Counselor writes their own assessment.
- No effect on SOS, appointment outcomes, access, or clinical decisions.
- Visible movements do not establish the student's emotional state.

## Validation status

The automated protocol, reducer, summary, lifecycle, and UI checks pass. Real-device validation of smile, brow raise, and brow furrow (lighting, glasses, head turns, talking, deliberate movements, false triggers) and a two-browser rehearsal remain required before claiming detector reliability. If a movement does not pass, disable it or use only the clearly labeled simulated timeline demonstration; live detection remains unfinished.

See the detailed [product and summary plan](FACIAL_OBSERVATION_PROTOTYPE_PLAN.md) and [implementation plan](FACIAL_OBSERVATION_IMPLEMENTATION_PLAN.md).
