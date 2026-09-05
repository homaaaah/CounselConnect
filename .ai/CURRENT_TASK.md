# CounselConnect — Current Task

**Status:** COMPLETED
**Risk class:** HIGH (authentication/authorization, cookies, role enforcement)

## Objective (ADR-019, user-approved 2026-09-05)

Real login/logout/refresh with MySQL-backed opaque sessions in secure HttpOnly cookies, CSRF protection, Argon2id password hashing (transparent bcrypt upgrade), role-based endpoint enforcement replacing the temporary X-Admin-Key dev guard. ADR-P01 recorded as APPROVED in `.ai/DECISIONS.md` (ADR-019); removed from Pending.

## Delivered

**Backend**
- `core/security.py`: Argon2id hash/verify; bcrypt verify + `needs_rehash` upgrade; 256-bit `secrets` credentials; SHA-256 digests; constant-time compares.
- `modules/auth/`: `schemas.py` (LoginRequest/SessionUser/AuthResponse), `service.py` (login by student-number-or-email with timing parity, session issue, single-session policy, cookie set/clear with settings-driven `secure`, CSRF rotation, authenticate_request with 1h idle / 12h absolute / CSRF / status checks, logout), `router.py` (login, refresh, logout, me, csrf).
- `shared/dependencies.py`: `get_current_user`, `require_roles`, `require_counselor` (CSRF enforced on unsafe methods only).
- `modules/enrollment_verification/router.py`: all reviewer endpoints COUNSELOR-gated; COR upload STUDENT-gated with session identity (`student_user_id` query param gone).
- `modules/accounts/router.py`: removed the `/accounts/lookup` enumeration endpoint.
- `config.py`: `cookie_secure` setting (default False for localhost, True behind HTTPS); removed dead `dev_admin_key`.
- `dev_seed.sql`: dev counselor `counselor@ucc.edu.ph` / `counselor-dev-2026` (Argon2id; ADR-005 developer-created; rotation warning).
- `requirements.txt`: `argon2-cffi>=23.1`.

**Frontend**
- `apiClient.ts`: `credentials: "include"`, in-memory CSRF token attached to unsafe methods when present (login/register exempt), 401 clears token.
- `features/auth/`: `useLogin` (real flow), `useSession` (restore via `/auth/me` + `/auth/csrf` recovery after reload; logout).
- `features/enrollment/`: reviewer console session-based (no dev-key UI, blob-fetch PDF preview); `useCorUpload` session identity.
- `LoginPage`: role-based redirect (COUNSELOR → `#review`).

**Tests** — `tests/unit/test_auth_flow.py` (16 tests): identifier lookup, same-error rule, allowed statuses + guard constant, bcrypt→Argon2 upgrade, single-session revocation, cookie flags (HttpOnly/SameSite/Path/Max-Age), me/refresh/logout flows, CSRF on refresh + approve, per-endpoint role gates (pending/history/cor/approve/reject), session-identity COR upload, idle + absolute expiry, never-sliding absolute, digest-only storage.

**Docs** — SECURITY.md (implemented ADR-019 section, allowed-statuses fix), TEAM_SETUP_GUIDE.md (counselor sign-in flow, troubleshooting, no more dev-key), `contracts/openapi.json` regenerated (20 paths; +auth/csrf, −accounts/lookup).

## Review (HIGH-risk fresh pass — read-only agent)

REQUEST_CHANGES blockers all fixed: (1) client CSRF guard no longer blocks public POSTs; (5) `/auth/csrf` re-issues token after reload (logout-after-reload works); (2) enumeration endpoint removed; (3) dummy-verify timing parity; (7) settings-driven Secure cookie; plus #4 role redirect, #6 true idle-expiry moment, #14 STUDENT role gate, #9 dead config/stale docstrings, #12 stale hook, #10 Argon2 comment, #11 docs statuses, test gaps (cookie flags, per-endpoint gates, CSRF-on-approve, guard constant).

Remaining from review, deliberately deferred: GUIDANCE_STAFF assigned-case review endpoints (needs assignment data model wiring — separate task); scheduled `delete_expired_sessions` cleanup job (needs a scheduler story); OpenAPI security schemes annotations (cosmetic); FR-AUTH-03 five-minute warning UI rendering (timestamps already returned).

## Verification (all executed 2026-09-05)

1. `pytest app/tests -q` → **31 passed** (16 auth + 10 sessions + 5 originals) against real MySQL test schema.
2. Live e2e (uvicorn + curl cookie jar): login (cookie HttpOnly/SameSite=lax/Max-Age=43200), /auth/me, /auth/csrf recovery, refresh (CSRF+expiries), logout revokes (401 after), wrong password 401 same envelope, timing parity ~equal (401ms vs 354ms incl. network), student-number login, student 403 on all reviewer endpoints, student COR upload 201 via session, counselor queue 200, lookup endpoint 404.
3. Frontend `npm run build` clean; login page role-redirect wired.
4. OpenAPI regenerated and asserted.

## Human decisions

- ADR-P01 approved by user (built as ADR-019). Password-reset flow (FR-AUTH-04) is the next auth task, separately.
- Dev counselor password `counselor-dev-2026` must be rotated before any real deployment (documented in seed + setup guide).
