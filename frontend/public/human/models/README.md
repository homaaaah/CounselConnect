# Local Human suggestion models

Served from the application origin so Phase 2 suggestions never request a third-party model
host.

| File | Purpose |
|---|---|
| `blazeface.bin` + `blazeface.json` | Human face detector |
| `emotion.bin` + `emotion.json` | Human expression classifier |
| `models.json` | Model manifest from the installed package |

## Provenance

- Package: `@vladmandic/human` `3.3.6` (MIT).
- Source: the installed npm package `models/` directory; files copied without modification.
- Human runs locally on the same captured frame as MediaPipe. No frames, raw scores, or
  landmarks leave the Student device; only the top suggestion label or an unavailable reason
  is relayed.
- Check the upstream Human model cards/license before redistribution. Phase 2 is enabled only
  by the `VITE_FACIAL_HUMAN_SUGGESTIONS=true` build flag and should stay off by default.

## Update procedure

1. Pin the new `@vladmandic/human` version.
2. Copy the matching `blazeface.*`, `emotion.*`, and `models.json` files.
3. Re-run the focused facial-observation tests and the production build.
4. Re-run the two-device flag-off/flag-on rehearsal.
