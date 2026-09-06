# CounselConnect — Current Task

**Status:** COMPLETED
**Risk class:** HIGH (authentication, COR privacy, concurrent decisions, test isolation)

## Objective

Implement the seven issues identified in the 2026-09-06 review, as requested by the user, within the existing Markdown contracts and approved ADR-004/005/019 rules.

## Context and scope

Primary route: security. Owning contracts: `docs/SECURITY.md`, `docs/REGISTRATION_VERIFICATION.md`, `docs/USER_ROLES.md`, `docs/API_CONTRACT.md`; naming follows `.ai/NAMING_CONVENTIONS.md`.

- Prevent student-number collisions from shadowing staff email logins.
- Restore session/CSRF before protected UI actions; preserve CSRF across tabs and expose real sign-out.
- Enforce seven-day COR expiry, retain failed cleanup metadata, and run automatic cleanup/retries.
- Serialize COR submissions/decisions; commit decisions before irreversible file deletion.
- Isolate all DB tests from the ordinary application database, storage, and SMTP.
- Sanitize validation errors and share registration validation between JSON and multipart.
- Add focused privacy/concurrency/frontend regressions and regenerate OpenAPI.

Preserve existing structure-documentation changes. No role expansion, new database tables, production data migration, or approval of pending policy choices.

## Delivered

- Staff email cannot be shadowed by a student number; registration rejects existing staff-identifier collisions. Student login follows the approved student-number rule. Unknown logins reuse a precomputed dummy password hash.
- The app restores user/CSRF together before mounting the reviewer, keeps recovery stable across tabs, and supports real sign-out. Late responses cannot overwrite a newer login token. Session recovery does not count as genuine activity.
- COR submissions and decisions use a consistent Student/verification lock order. Decisions commit before file deletion. Expired evidence is denied, failed deletion retains retry metadata, and the application worker performs expiry/retry passes every minute. Interrupted upload markers are reconciled by TTL. Preview blobs are released after decisions/unmount, including in-flight preview races.
- Test fixtures require an explicit test URL, create/drop only their own random schema, override application connections, and isolate file stores/SMTP. JSON/multipart registration share validation; errors omit submitted inputs and validator context.
- Owning security/registration/API/database/setup docs and the context route are updated. OpenAPI is regenerated; `backend/scripts/export_openapi.py --check` provides a repeatable drift check. Existing structure-guide changes are preserved.

## Verification (executed 2026-09-06)

- Backend: **66 passed**, no skips, against a unique disposable loopback MySQL schema; application data was not used by the test fixtures. Covers failed deletion/retry, TTL, original replacement deadlines, commit failure, simultaneous approve/reject (both winners), authorization, validation redaction, and CSRF recovery.
- The backend suite includes a real React-to-FastAPI HTTP flow: login → lose component/CSRF memory while retaining the cookie → restore → approve → logout. It runs against the isolated schema and temporary COR store.
- Frontend: **8 passed** with the actual TS/TSX components and API client; `npm run build` passed (TypeScript + Vite production output).
- Generated OpenAPI matches the application; focused Ruff checks and `git diff --check` passed.
- One existing Starlette/TestClient deprecation warning remains. The HTTP/component integration test is not a full browser/device test.

## Remaining project decisions outside this fix

Guidance Staff assignment wiring, password reset, session-row cleanup scheduling, idle-warning UI, and other pending ADRs remain separate work. Existing provisional PDF/size rules are unchanged. Physical cleanup requires an application/cleanup process to run; failed I/O is tracked and retried, not falsely reported as successful.

Cleanup does not sweep unrelated or previously untracked legacy files; any reconciliation of applicant files that lost metadata before this fix is separate authorized maintenance. No production migration or deployment was performed.
