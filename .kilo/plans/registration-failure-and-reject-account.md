# Plan: No account on technical screening failure + split "Reject account" / "Re-upload COR"

**Status:** implementation-ready
**Risk:** HIGH (destructive self-deletion of accounts + PII; changes the registration failure contract)
**Implement with:** an implementation-capable agent (this plan contains no code changes).

## Goal

1. **Registration must not create an account when the screening process technically fails.** If `engine.derive_outcome` returns `FAILED` (the `TECHNICAL_ERROR` decoder/processing case), persist nothing and return a retryable error. `NEEDS_RESUBMISSION` (unreadable/low-confidence/barcode document issues) still creates the `PENDING_VERIFICATION` account so the Student can retry.
2. **Split the combined "Reject and re-upload" action into two explicit choices** on both the review and re-upload steps: **Re-upload COR** (keep the account, upload a new COR) and **Reject account** (delete the account and its credentials so the email/student number are freed).

## Locked decisions

1. **Only technical `FAILED` skips account creation.** `engine.derive_outcome(...) == ("FAILED", "TECHNICAL_ERROR")` -> no user, no screening, no file; `NEEDS_RESUBMISSION` and `AWAITING_CONFIRMATION` still create the account.
2. **"Reject account" is a full deletion**: the `users` row, all their `cor_screenings` + `cor_screening_files`, `student_profiles`, `user_sessions`, and any `profile_change_requests`; the private COR bytes on disk; then one `account_rejected` audit event. The email and student number become reusable for a fresh registration.
3. **Both choices appear on the review/confirm step and the re-upload step** in the modal and on the signed-in `#registration` page.
4. **"Re-upload COR" goes straight to the upload form**; the upload itself uses the existing `POST /cor-screenings/resubmit` (which accepts `AWAITING_CONFIRMATION`). The user-facing `POST /cor-screenings/reject` action is retired from the UI; the endpoint is kept for compatibility and marked deprecated.
5. **Assumed defaults (veto if wrong):**
   - Register technical failure returns `503 SCREENING_FAILED` ("We could not process your registration form. Please try again."), and the client keeps the form so the Student can resubmit.
   - New endpoint `POST /cor-screenings/reject-account` (Student session or `X-COR-Token`, `204`), scoped to the verification phase (`account_status` in `PENDING_VERIFICATION`/`VERIFICATION_EXPIRED`).
   - A technical `FAILED` during **resubmit** keeps the account (it already exists) — only first registration is account-free on failure.
   - "Reject account" is destructive and needs a two-step confirm in the UI.

## Out of scope

- Deleting accounts outside the verification phase (active/expired self-deletion), and Admin-initiated deletion.
- Removing the `POST /cor-screenings/reject` endpoint or the `REJECTED_BY_STUDENT` status (kept for compatibility; UI stops using it).
- Changing the existing technical-`FAILED` semantics for resubmit/recovery (ADR-030 item 8 remains).
- Any schema/migration change: none required.

## Backend

### Registration (`backend/app/modules/cor_screening/service.py::register_with_cor`)
- After `screen_pdf` and the `student_no` normalization (before user creation), compute `status, failure = engine.derive_outcome(result, get_settings())`.
- If `status == "FAILED"`: `self._delete_cor_bytes(storage_key)` and raise `AppError(code="SCREENING_FAILED", message="We could not process your registration form. Please try again.", status_code=503)`. **No user/screening/file rows are created.**
- Otherwise proceed unchanged (user -> `PROCESSING` screening -> commit -> `_apply_result` -> commit); `_apply_result` re-derives the same non-`FAILED` status, so the existing observability path (ADR-030 item 9) is preserved for successful/document-failure cases.

### New reject-account action (`cor_screening/service.py` + `router.py` + `schemas.py`)
- `CorScreeningService.reject_account(student, screening=None) -> None`, called from the router through the existing `get_screening_actor` (token or session).
  - Eligibility: `student.account_status in ("PENDING_VERIFICATION", "VERIFICATION_EXPIRED")`; otherwise `409 PROFILE_EDIT_NOT_ALLOWED`-style code, e.g. `ACCOUNT_NOT_REJECTABLE`.
  - Gather storage keys from every `cor_screening_files` row of the Student (and `.pending` markers).
  - Record the audit event first (`account_rejected`, `target_type="user"`, `target_id=student.user_id`) so the actor FK nulls out on delete.
  - Delete in FK-safe order: legacy `enrollment_verifications` (+ files) if any -> `cor_screenings` (cascades `cor_screening_files`; `profile_change_requests` cascade) -> `student_profiles`/`user_sessions` (cascade) -> `users`. `BaseRepository.delete(...)` / explicit deletes on the session; single `commit()`.
  - Best-effort delete the file bytes on disk after the commit; log `cor_screening_account_reject_file_cleanup_retry_required` on failure (rows are gone, so no automatic retry).
  - Return `None` (router returns `Response(status_code=204)`).
- `POST /cor-screenings/reject-account` with `ScreeningActor`, `status_code=204`, summary "Student: cancel registration and delete the account (ADR-033)".

### Router docstring
- Update the module docstring to list `request-edit` and `reject-account`, and note `reject` is deprecated for the UI.

## Frontend

- `features/accounts/useRegistration.js`
  - Add `SCREENING_FAILED` to `ERROR_MESSAGES` (retry copy). Registration no longer returns a `FAILED` screening; `handleSubmit` shows the error and stays on the form.
- `pages/RegisterPage.jsx` (review/confirm step)
  - Replace the single "Reject and re-upload" button with two: **Re-upload COR** (calls `setPhase("resubmit")`, no request) and **Reject account** (`handleRejectAccount`).
  - `handleRejectAccount`: two-step confirm -> `POST /cor-screenings/reject-account` with `tokenHeaders` -> on success clear the token and show a "Registration cancelled and details deleted" state with a Sign in / Back action.
  - Add a **Reject account** button to the resubmit step as well.
- `features/accounts/useCorScreening.js`
  - Add `rejectAccount()` (`POST /cor-screenings/reject-account`); add error copy for `ACCOUNT_NOT_REJECTABLE`/`SCREENING_FAILED`; stop using `reject()` in the UI (keep the function or remove it).
- `pages/student/RegistrationStatusPage.jsx`
  - Replace the combined reject action with the same two: **Re-upload COR** (no backend call; show the upload form) and **Reject account** (confirm -> `state.rejectAccount()` -> `onRejected()` to clear the session).
- Reuse the existing confirm/upload markup and CSS classes; the destructive action should be visually distinct and confirm-gated.

## Documentation

- `.ai/DECISIONS.md` — add **ADR-033**: registration failure isolation (technical `FAILED` persists no account) and Student-initiated account rejection (full deletion, frees email/student number, audited). Note the `PROCESSING` observability now applies only to outcomes that create/persist a screening.
- `docs/REGISTRATION_VERIFICATION.md` — update the flow: technical failure -> no account; two choices on review/re-upload; reject-account deletion semantics.
- `docs/API_CONTRACT.md` — register row: technical `FAILED` -> `503 SCREENING_FAILED`, no account; add `POST /cor-screenings/reject-account` (204); mark `POST /cor-screenings/reject` deprecated for UI use.
- `docs/SECURITY.md` — Student self-deletion control: pre-active only, destructive, audited, releases the email/student number; note the private COR bytes are removed.
- `docs/WORKFLOWS.md` — account-lifecycle branch for reject-account and the no-account-on-technical-failure rule.
- `.ai/NAMING_CONVENTIONS.md` — error code `SCREENING_FAILED`, `ACCOUNT_NOT_REJECTABLE`; audit event `account_rejected`.
- `docs/USER_ROLES.md` — Student may reject/delete their own pending registration.
- `.ai/CURRENT_TASK.md` — new task entry.

## Tests

Backend (MySQL-gated, mirror existing patterns):
- Register with a result that `derive_outcome` classifies as `FAILED` (e.g. `barcode_status = engine.BARCODE_NOT_PROCESSED`) -> `AppError SCREENING_FAILED`, **no** `users`/`cor_screenings`/`cor_screening_files` rows, file bytes gone, and the same email can register again.
- Register with `NEEDS_RESUBMISSION` still creates the `PENDING_VERIFICATION` account.
- `reject_account` (token path and session path) deletes user/profile/screening(s)/files/sessions/pending change requests; email + student number reusable; `account_rejected` audit exists; private file bytes removed.
- `reject_account` with an `ACTIVE` student -> `409 ACCOUNT_NOT_REJECTABLE`; invalid/empty token -> `401 INVALID_VERIFICATION_TOKEN`.
- HTTP: `POST /cor-screenings/reject-account` with `X-COR-Token` -> `204` and the row is gone; counselor session -> `403` (role/eligibility).

Frontend (`node --test` CJS):
- Modal review step shows two separate buttons; **Re-upload COR** moves to the upload step **without** calling `/cor-screenings/reject`; **Reject account** posts to `/cor-screenings/reject-account` after confirm and shows the cancelled state.
- The resubmit step also exposes Reject account.
- Registration `SCREENING_FAILED` shows the retry message and stays on the form.
- `#registration` page: Re-upload COR shows the upload form; Reject account calls the endpoint and triggers the logout callback.

OpenAPI regenerated and `--check` passes.

## Validation commands

- `backend/`: `COUNSELCONNECT_TEST_DATABASE_URL=... pytest app/tests -q`.
- `backend/`: `python scripts/export_openapi.py` + `--check`.
- `frontend/`: `npm test` (expect only the 3 pre-existing calendar failures) + `npm run build`.
- Manual smoke: force a technical failure and confirm no account exists and the email can re-register; on a `NEEDS_RESUBMISSION` account, use Re-upload COR (new COR accepted) and Reject account (account + COR gone, email reusable).

## Risks / notes

- **Destructive + PII:** account deletion must be pre-active only, confirm-gated, and audited; never expose the deleted data afterwards. The audit event survives (actor FK nulls).
- The `enrollment_verifications` legacy table has a RESTRICT FK; delete any rows for the Student first or the user delete fails.
- Private COR bytes are outside the DB transaction; deletion is best-effort after commit, mirroring the existing cleanup pattern.
- `PROCESSING` observability for first registration only applies to outcomes that persist a screening.

## Ordered tasks

1. Backend: technical-`FAILED` guard in `register_with_cor` + `SCREENING_FAILED`.
2. Backend: `reject_account` service (FK-safe deletion, audit, file cleanup) + `POST /cor-screenings/reject-account` + router docstring.
3. Backend tests (registration failure, reject-account token/session/eligibility/invalid-token); run the MySQL suite + OpenAPI.
4. Frontend: registration `SCREENING_FAILED` handling; `useCorScreening.rejectAccount`; RegisterPage and RegistrationStatusPage two-choice flow + reject-account confirm/cancelled state.
5. Frontend tests; run `npm test` + `npm run build`.
6. Docs: ADR-033 + REGISTRATION_VERIFICATION, API_CONTRACT, SECURITY, WORKFLOWS, NAMING_CONVENTIONS, USER_ROLES, CURRENT_TASK.
7. Final read-only review focused on the destructive deletion (authorization, FK order, PII/file cleanup, eligibility) and the no-account-on-failure contract.
