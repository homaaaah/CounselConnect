# Local expression model weights

These files are served from the application origin so the optional expression
cue can load without a third-party request.

| File | Purpose |
|---|---|
| `tiny_face_detector_model-weights_manifest.json` + `.bin` | TinyFaceDetector face detection |
| `face_expression_model-weights_manifest.json` + `.bin` | Seven-label face-expression classifier |

## Provenance

- Package: `@vladmandic/face-api` 1.7.15 (`model/` directory)
- Source: the installed npm package; the files are copied without modification.
- License: MIT (`@vladmandic/face-api`). The upstream project credits the
  original `face-api.js` by Vincent Mühler.
- Use: local browser inference only (ADR-025). No frames, landmarks, or
  embeddings are uploaded, stored, or logged.

## Update procedure

1. Update the npm dependency.
2. Copy the four files above from `node_modules/@vladmandic/face-api/model/`.
3. Re-run the focused expression tests and the production build.
