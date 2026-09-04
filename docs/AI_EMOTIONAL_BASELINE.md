# CounselConnect — Optional Local Expression Cue

“AI Emotional Baseline” is the adviser-required feature label. The implemented contract is narrower: optional local **facial-expression recognition** producing an Observed Expression Cue for an active Live Chat/SOS interaction.

```text
consent → camera ~3 seconds → local inference → allowlisted text cue
→ camera off → authorized Counselor read-only context → discard on close
```

## Invariants

- No identity facial recognition, raw media upload, cloud inference, embedding, database field/table, persistent client storage, history, diagnosis, or profiling.
- Scan is optional. Denial, timeout, poor input, unsupported device, or model failure yields “unavailable/no result,” releases the camera, and never blocks the underlying flow.
- Cue is session-only and never affects SOS scoring, alerting, availability, or fallback.
- Validate transmitted cue against an allowlist and keep it out of routine logs/analytics.

## Implementation gate

The local model/library and label set remain pending. Any candidate must be tested on target browsers/Capacitor devices for model size, latency, camera lifecycle, failure rate, lighting/pose/demographic sensitivity, and usefulness. Enable expression inference only—never identity/recognition modules.

## Required tests

No image/video network/storage path; camera release on success/failure/cancel; optionality; allowlist/read-only UI; discard on close; identical SOS result for every cue/absence; target-device performance.
