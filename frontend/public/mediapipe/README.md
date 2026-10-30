# Local MediaPipe face-observation assets

Served from the application origin so facial observation never requests a third-party
runtime or model host.

| File | Purpose |
|---|---|
| `wasm/vision_wasm_internal.js` + `.wasm` | MediaPipe Tasks Vision SIMD runtime |
| `wasm/vision_wasm_nosimd_internal.js` + `.wasm` | Non-SIMD fallback runtime |
| `face_landmarker.task` | Face Landmarker model (float16, version 1) |

## Provenance

- Runtime: `@mediapipe/tasks-vision` `0.10.22-rc.20250304`, Apache-2.0. WASM files copied
  from the installed npm package `wasm/` directory.
- Model: `face_landmarker.task` from
  `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`.
  Check the current MediaPipe model card and license before redistribution.
- Use: local browser inference only. Frames, landmarks, blendshape vectors, and model
  outputs stay in the Student's device. Only bounded movement/quality slots are sent to
  the assigned Counselor.

## Update procedure

1. Update the npm dependency and copy the matching `wasm/` files.
2. Download the pinned model revision and replace `face_landmarker.task`.
3. Re-run the focused facial-observation tests and the production build.
4. Record the detector version/threshold change in the implementation report.
