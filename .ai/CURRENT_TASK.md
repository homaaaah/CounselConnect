# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** In-modal enrollment verification with a one-time `X-COR-Token` and no auto-login (plan `.kilo/plans/inmodal-verification-token.md`).

## Objective

Registration must not sign the Student in. The whole verification (confirm / reject / re-upload a corrected COR / confirm again / activate) happens in the same registration modal, authorized by a one-time verification token instead of a session.

## Route

`registration` (`.ai/CONTEXT_MAP.md`) → `docs/REGISTRATION_VERIFICATION.md`, `backend/app/modules/cor_screening/`, `frontend/src/pages/RegisterPage.jsx`.

## In scope

- `cor_screenings` columns `verification_token_hash BINARY(32)` + `verification_token_issued_at DATETIME(6)`; migration `20261001_cor_verification_token`; conftest loader.
- Service: issue token on register/resubmit, resolve by token hash (student→screening lock order), rotate on resubmit, clear on activation/expiry.
- Router: `X-COR-Token` OR Student session on confirm/reject/resubmit; register response returns the token; no token GET.
- Frontend: remove auto-login/`setCsrfToken`, carry the token in memory, send `X-COR-Token`, done → Sign in.
- Backend + frontend tests; OpenAPI snapshot.
- Docs: ADR-031, `REGISTRATION_VERIFICATION.md`, `API_CONTRACT.md`, `SECURITY.md`, `NAMING_CONVENTIONS.md`, `WORKFLOWS.md`, `TEAM_SETUP_GUIDE.md`.

## Out of scope

- New token `GET` endpoint; no secrets in URLs.
- Session `#registration` fallback path (kept unchanged).
- Optional cleanup of the 3 pre-existing frontend calendar failures.

## Acceptance criteria

1. Register no longer signs the Student in; response includes `verification_token`.
2. Confirm/reject/resubmit accept a valid token with no session cookie; no CSRF applied.
3. Missing/expired/tampered/rotated-away token → 401 `INVALID_VERIFICATION_TOKEN` (never logged).
4. Token is SHA-256-hashed at rest, rotated on re-upload, destroyed on activation.
5. Resubmit returns a fresh rotated token; reject keeps the current token.
6. Existing session-path endpoints and tests remain unchanged.

## Planned verification

- Backend `pytest app/tests` (MySQL cases skip without `COUNSELCONNECT_TEST_DATABASE_URL`).
- `python scripts/export_openapi.py` regenerate + `--check`.
- Frontend `npm test` + `npm run build`.
- Fresh read-only review of the new unauthenticated path before acceptance.

## Actual verification

- Backend (no test DB): `pytest app/tests` → 83 passed, 130 skipped.
- Backend (MySQL test DB, `COUNSELCONNECT_TEST_DATABASE_URL` set): `pytest app/tests` → **213 passed**, 0 skipped. This is the first time the MySQL-gated suite actually ran; it had latent failures (see "Pre-existing defects found by running MySQL tests").
- Migration applied to the dev DB (`alembic upgrade head`): head is now `20261001_cor_verification_token`.
- OpenAPI: regenerated; `python scripts/export_openapi.py --check` passes (new `X-COR-Token` header + `verification_token` fields present).
- Frontend: `npm test` → 66 passed, 3 failed. The 3 failures are the known `appointments.test.cjs` calendar date-rot cases (unrelated, pre-existing). `npm run build` succeeded.
- HIGH-risk independent read-only review (token path): completed. No HIGH defect. Fixed the one MED correctness gap (present-but-empty `X-COR-Token` fell through to session auth); added the missing HTTP-level tests.
- Manual browser E2E against the dev DB: confirmed working (register while signed out → inline confirm → "Account activated" → Sign in; reject → re-upload).
- Docs updated to match: ADR-031 in `.ai/DECISIONS.md`; `REGISTRATION_VERIFICATION.md`, `API_CONTRACT.md`, `SECURITY.md`, `NAMING_CONVENTIONS.md`, `WORKFLOWS.md`, `TEAM_SETUP_GUIDE.md`.

## Pre-existing defects found by running the MySQL suite

These were never exercised before (the suite skips without a test DB). Fixed as part of "run the tests":

- **Test harness could only create schemas via the `mysql` system schema.** `conftest.py` and `test_recurring_schedules.py` connected the admin engine to `database="mysql"`, which a restricted test account (grants only on `counselconnect_test%`) cannot access. Changed to `database=""` (no default schema). Note `URL.set(database=None)` is a silent no-op.
- **Real production bug (review finding #7): resubmit after an expired window violated `chk_cor_screenings_timeline`.** Moving `submitted_at` forward left the older `processing_started_at`/`processed_at`, so MySQL rejected the UPDATE (500). `_resubmit_core` now also sets `processing_started_at = now` and `processed_at = None` with the fresh window.
- **Stale test data in `test_cor_screening_lifecycle.py`:** confirm payloads used `last_name="Dela Cruz"`/no middle name while `split_name` yields `("Juan","Dela","Cruz")`; missing `academic_period`; `.exists()` called on a `str` (`_storage_path` returns `str`); an expired-evidence test did not age the file row; the directory search asserted a student-number hit before a profile exists.
- **Stale auth test:** `test_student_login_uses_student_number` asserted email login fails, contradicting the #7 email-or-student-number change (renamed/adjusted).

## Residual risks / not changed

- LOW: `resolve_verification_token` checks only `role_code == "STUDENT"`, not `account_status`; equivalent today because the `users.account_status` CHECK allows only the three login-allowed statuses.
- LOW: `verification_token_issued_at` is stored as audit metadata; expiry is bound to `submitted_at + 7d` per the plan.
- LOW: admin recovery (`recover_student`) does not clear the token (plan mandates clearing only on PASSED/TTL).
- LOW: a token committed in the PROCESSING commit is not returned if the finalize commit fails; it stays valid but unknown (TTL-bounded).

## Unresolved human decisions

- Admin recovery policy: `recover_student` currently leaves an unexpired token valid (the Student continues the normal inline re-upload). Clear the token on recovery only if recovery must invalidate any outstanding modal credential.
- Optional: fix/quarantine the 3 pre-existing `appointments.test.cjs` calendar date-rot failures so `npm test` exits clean.
