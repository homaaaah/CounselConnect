# CounselConnect — Current Task

**Status:** COMPLETED (2026-09-11)
**Risk class:** MEDIUM (localized client error-path hardening; no API/schema/auth boundary change)

**Task:** Harden frontend `ApiError` against non-envelope error responses so the converted `apiClient.js` never crashes when a server/proxy returns a JSON body without the standard `{ "error": { code, message, details } }` envelope (e.g. FastAPI 405 `{"detail": "Method Not Allowed"}`, unknown-route 404s, gateway errors).

**Route (CONTEXT_MAP):** `project` → `.ai/PROJECT.md`; affected code: `frontend/src/services/apiClient.js`, `frontend/tests/session.test.cjs`.

## Objective (observable)

A non-envelope JSON error body throws a safe `ApiError` carrying `code: "REQUEST_FAILED"`, the body's `detail` string as message when present, and no constructor crash; standard envelopes and unparseable bodies (`NETWORK_ERROR`) behave exactly as before.

## Outcome

- `normalizeErrorBody` added before the `ApiError` constructor: standard envelopes pass through with exact code/message/details (message must be a string; a non-string code degrades to `REQUEST_FAILED`); non-envelope JSON with a `detail` string becomes `REQUEST_FAILED` + that detail; anything else (unparseable, empty, missing `error`) becomes `REQUEST_FAILED`/"Request failed.".
- New session-suite test "non-envelope error bodies still throw a safe ApiError" covering all three shapes (405 detail, standard envelope, unparseable 502).

## Verification (run 2026-09-11)

- `npm test` — 30/30 PASS (29 existing + 1 new; envelope pass-through assertions intact: `TEST_ERROR`, CSRF, booking-conflict flows).
- Live backend probe: `PUT /accounts/programs` (real FastAPI 405 `{"detail":"Method Not Allowed"}`) now rejects with `{"status":405,"code":"REQUEST_FAILED","message":"Method Not Allowed","details":{}}` — previously a `TypeError` crash (pre-existing since the TS original; surfaced by the JS-migration verification).
- `npm run build` — PASS (209.52 kB, clean).
- MEDIUM self-review of diff: minimal, localized; 401 token-clear logic and CSRF header logic untouched.

## Remaining limitations

- None known for this fix. (Broader live-HTTP suites still need a backend loopback server; not run here.)

## Human decisions

- (none outstanding)
