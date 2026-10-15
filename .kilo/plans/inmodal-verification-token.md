# Plan — In-modal enrollment verification without auto-login

Status: READY FOR APPROVAL (HIGH risk — new auth path)
Goal: Registration must **not** sign the student in. The entire verification (confirm / reject / re-upload a corrected COR / confirm again / activate) happens in the **same registration modal**, authorized by a **one-time verification token** instead of a session.

## Decisions (approved)

- **No auto-login** after account creation.
- **One-time verification token** returned once by the registration call, sent as header **`X-COR-Token`**; authorizes only confirm/reject/re-upload for that screening. No secrets in URLs.
- Token valid until the screening is `PASSED` or its 7-day TTL expires; **rotated on re-upload**, **destroyed on activation**.
- After activation: modal shows **"Account activated" + Sign in button** (no auto-login).
- Keep the signed-in `#registration` page (session path) as a fallback for returning pending students.

## Backend

1. **Migration** `20261001_cor_verification_token` (down_revision `20260930_superadmin_role`): add to `cor_screenings` — `verification_token_hash BINARY(32) NULL`, `verification_token_issued_at DATETIME(6) NULL`, index `idx_cor_screenings_token (verification_token_hash)`. Update `backend/app/tests/conftest.py` to apply it.
2. **Model/schema**: add the two columns; `RegistrationWithCorResponse` gains `verification_token: str`.
3. **Service** (`CorScreeningService`):
   - `register_with_cor`: generate `secrets.token_urlsafe(32)`, store `sha256` on the screening, return the raw token.
   - `resubmit`: rotate the token (new raw token returned) and re-hash.
   - `confirm`: null the token hash (already `PASSED`).
   - `cleanup`/expiry: null the token hash when a screening becomes `FAILED`.
   - Add `resolve_verification_token(token) -> CorScreening` (lock; rejects missing/expired/`PASSED`/tampered with `INVALID_VERIFICATION_TOKEN` 401).
   - Refactor `confirm`/`reject`/`resubmit` so their core takes the resolved screening + student; session wrappers keep current behavior; token wrappers call the same core.
4. **Router** (`cor_screening`):
   - Register response includes `verification_token`.
   - `POST /cor-screenings/confirm|reject|resubmit`: accept **either** a Student session **or** header `X-COR-Token`. Implement a dependency `get_screening_actor` that prefers the token when present, else falls back to `require_roles("STUDENT")`. Token requests are cookie-less, so CSRF does not apply; never log the header.
   - Do not add a token `GET` (the modal already has the screening from register/resubmit responses).
5. **Config**: token is tied to the existing 7-day `expires_at`; no new setting required (optionally `cor_verification_token_ttl` if we want it separate — default: reuse screening TTL).
6. **Tests**: register returns a token; confirm with `X-COR-Token` works with **no session**; invalid/expired token → 401; token dies after confirm; re-upload rotates the token; existing session-path tests unchanged.

## Frontend

1. `useRegistration.register`: **remove** the `/auth/login` auto-sign-in and `setCsrfToken`/`auth`; return `verificationToken` from the register response; `canConfirm = outcome === "AWAITING_CONFIRMATION"`.
2. `apiClient.request`: allow passing custom headers (token header); never persist or log it.
3. `RegisterPage`: keep the single card (`form → confirm → resubmit → done`).
   - Store the token in component state (memory only).
   - `confirm`/`reject`/`resubmit` send `X-COR-Token`; a re-upload updates the token from the response.
   - Remove the auto-login/`onSignedIn` usage; remove the `#registration` "Continue" fallback for token-authorized outcomes.
   - `done` (activated): success message + **Sign in** button → switch to the student sign-in (`onSwitchToLogin` / `#login`).
4. Keep `RegistrationStatusPage` (`#registration`) unchanged for the logged-in fallback.

## Verification

- Backend: `pytest app/tests` (expect current 80 + new token tests); `export_openapi.py` regenerate + `--check`.
- Frontend: `npm test` (expect existing pass count, no new failures) + `npm run build`.
- Manual: register (not logged in) → confirm with token → "Account activated" → Sign in; reject → re-upload inline → confirm.
- HIGH risk: run a fresh read-only review of the token path (authorization, expiry, rotation, logging) before acceptance.

## Risks / notes

- New unauthenticated authorization path → must fail closed, be high-entropy, hashed at rest, single-purpose, expiring, and never logged.
- If the student closes the modal before confirming, the token is lost — they recover by signing in (email/student number) and using `#registration` (session path). Document this.
- Token is returned in the register/resubmit response body; ensure it is excluded from logs and error messages.
- Docs: extend `REGISTRATION_VERIFICATION.md`, `API_CONTRACT.md`, `SECURITY.md`, add **ADR-031** (or extend ADR-029) for the token + no-auto-login, and note `X-COR-Token` in `NAMING_CONVENTIONS.md`.

## Open items (confirm during execution)

- Header name `X-COR-Token` (vs `X-Verification-Token`).
- Reject in-modal: with no session, reject must use the token (no logout concept anymore). Confirm this replaces the earlier "auto-logout on reject".
