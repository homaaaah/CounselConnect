# CounselConnect — Registration and Enrollment Verification

## Contract

**Implementation versus target:** This page describes the existing registration flow. The agreed target for corrections, versions, private evidence, and account management is in [Registration Information Corrections and Users Management](REGISTRATION_CORRECTIONS.md). Its explicitly marked target rules supersede conflicting legacy wording below; those changes are not implemented yet.

Student registers with personal email, password, and the **current COR only** (ADR-029). The COR is the source of truth for the academic fields. A new account is `PENDING_VERIFICATION` and has no normal Student access.

```text
validate credentials + COR PDF
→ automate screening (format score + OCR extraction + embedded barcode)
→ AWAITING_CONFIRMATION  (clean screening)
   or NEEDS_RESUBMISSION (unreadable / low score / missing / barcode failure)
   or FAILED (technical)  → NO account is created; the Student retries (`SCREENING_FAILED`)
→ Student confirms, requests an edit, re-uploads, or rejects the account
→ account ACTIVE + valid_until, screening PASSED; COR deleted unless an exact pending correction retains it within its original seven-day deadline
```

The confirmation step appears **inline on the registration form** (prototype-style), but registration does **not** sign the Student in (ADR-031). The register response returns a one-time `verification_token`; the client sends it in the `X-COR-Token` header to authorize confirm/reject/re-upload for that screening, so the whole flow completes in the same card without a session. If the screening needs resubmission, the same card shows the re-upload step. The signed-in `#registration` page remains the fallback for a Student who loses the modal token (e.g. closes the tab): they sign in with their registration email or student number and use the session-authorized endpoints.

There is no human approval queue for activation. A screening is `AWAITING_CONFIRMATION` only when the format score and extraction confidence meet the configured thresholds **and** the embedded barcode decodes and matches the extracted student number. Anything less is `NEEDS_RESUBMISSION` and the Student re-uploads. A **technical** failure (`FAILED` / `TECHNICAL_ERROR`) creates **no account** (ADR-033): the uploaded COR is discarded and the API returns `503 SCREENING_FAILED` so the Student retries later, leaving the email/student number free. If the screening tooling is unavailable, registration likewise fails closed (`SCREENING_UNAVAILABLE`) and never activates an account.

Students sign in with their registration email or their student number (ADR-019/ADR-030).

The confirming Student must supply a strict UCC Student Number and active reference campus/program. Plain confirmation rejects changes to extracted values (`FIELD_MISMATCH` / `STUDENT_NUMBER_MISMATCH`). The existing request-edit action separately permits proposed names/year level/section while activation uses extracted values; Student Number, academic period, and mapped campus/program remain protected. Only unmapped campus/program choices are registration selections. Reject account remains pre-active only, and re-upload remains available when resubmission is required. Extracted names never create reference rows.

`AWAITING_CONFIRMATION` requires every required field (student number, name, course/program, year, section) to be present, plus a format score and extraction confidence at or above the thresholds, and a decoded barcode consistent with the extracted student number. The barcode's academic-period value is cross-checked against OCR when both are present, and the decode result/confidence is recorded. `valid_until` uses the enrollment-validity date read from the COR when it is still in the future, otherwise a 12-month default.

If an open screening is still pending after seven days: the screening becomes `FAILED`, the COR is deleted, and the account stays `PENDING_VERIFICATION`. Student confirmation sets account `ACTIVE` plus `valid_until`; when that date passes, set `VERIFICATION_EXPIRED`; the Student may submit a new current COR to renew. Never infer graduation from year level.

## File controls

- Allowlist type/size; inspect signature/MIME; randomize storage key.
- Keep outside public/static paths; authorize every read; never expose storage paths.
- Implemented pending-correction exception: retain only the exact COR for a versioned pending request until decision/replacement or the original seven-day deadline; no-change confirmation deletes immediately. Expiry returns the correction without restricting otherwise valid enrollment. See `REGISTRATION_CORRECTIONS.md`. Record/retry/alert cleanup failure.
- Exclude temporary files from long-lived backups where feasible.
- MySQL keeps screening status, scores, extracted fields, `valid_until`, and cleanup metadata—not document bytes. Raw OCR text and raw barcode payloads are never stored or logged; only a SHA-256 digest of the barcode payload.

## Screening statuses and failure codes

- Statuses: `PROCESSING`, `AWAITING_CONFIRMATION`, `PASSED`, `NEEDS_RESUBMISSION`, `FAILED`. The record is committed as `PROCESSING` before it is resolved (ADR-030).
- Barcode statuses: `NOT_PROCESSED`, `NOT_FOUND`, `UNREADABLE`, `INVALID_FORMAT`, `DECODED`, `MISMATCH`.
- Failure codes: `UNREADABLE_DOCUMENT`, `LOW_FORMAT_SCORE`, `MISSING_REQUIRED_FIELDS`, `LOW_EXTRACTION_CONFIDENCE`, `BARCODE_*`, `TECHNICAL_ERROR` (→ `FAILED`), `FIELD_MAPPING_FAILED`, `REJECTED_BY_STUDENT`, `ADMIN_RECOVERY`.
- Confirmation codes: `STUDENT_NUMBER_MISMATCH` (number differs from the screened value) and `FIELD_MISMATCH` (any verified field differs).
- Authorization codes: `INVALID_VERIFICATION_TOKEN` (401) for a missing, unknown, rotated-away, expired, or tampered `X-COR-Token`; `SCREENING_FAILED` (503) when a technical failure created no account; `ACCOUNT_NOT_REJECTABLE` (409) for self-cancellation of an active account.

## One-time verification token (ADR-031)

- Registration returns `verification_token` once in the response body (`Cache-Control: no-store`); `resubmit` rotates it and returns the new value. The client keeps it in memory only and sends it in the `X-COR-Token` header. There is no token `GET`, and no secret ever appears in a URL or log.
- The token authorizes only `confirm`, `reject`, and `resubmit` for its own screening. Those endpoints accept **either** the token **or** an authenticated Student session; a present-but-invalid token fails closed and never falls back to the session.
- At rest only `sha256(raw)` is stored (`cor_screenings.verification_token_hash BINARY(32)`) plus `verification_token_issued_at`. The token uses a 256-bit random value and constant-time digest comparison.
- The token shares the evidence window (`submitted_at + 7 days`; no separate setting). It is rotated on every re-upload, destroyed on activation (`PASSED`), and destroyed when the screening reaches `FAILED` at TTL expiry (in both `resolve` and the cleanup worker). An expired token also retires its screening to `FAILED`.
- Token requests carry no session cookie, so CSRF does not apply; everyone else remains CSRF-bound. Resolve locks the Student row before the screening row, matching the session path.

## Student-requested profile edits (ADR-032; existing baseline)

Implemented: `POST /cor-screenings/request-edit` activates with extracted values and queues a separate `PENDING` request for differences in names, `year_level`, or `section`. No differences creates no request. Existing requests use `PENDING`/`APPROVED`/`REJECTED`; an active Superadmin lists and approves/rejects whole requests, with a rejection reason. New screening supersedes a pending proposal. The current code retains exact pending-correction evidence within its original deadline (Task 4.3); returned-request revision after activation remains unimplemented. Task 4.2 now records immutable extraction/baseline snapshots, version-1 metadata and an exact evidence reference for new changed submissions; older requests remain unknown. Task 4.1 fixes the missing-middle-name exception: adding or clearing a middle name is a proposal, while activation preserves the extracted value (including null). Plain confirmation rejects such changes with `FIELD_MISMATCH`. Required extracted values cannot be filled from proposals.

**AGREED, not implemented:** See [the owning correction contract](REGISTRATION_CORRECTIONS.md) for remaining manual return/resubmission, full Superadmin detail/private evidence, transactional decisions, and the approved pending-correction retention exception. Pending corrections do not restrict an otherwise eligible active Student. Superadmin approves consistency with the submitted COR, never University issuance or registration eligibility.

Task 4.1 normalization is implemented for supported editable fields: trim/collapse Unicode whitespace before length validation, preserve spelling, treat blank middle names as null, compare text by backend Unicode casefold, and require an integer year level from 1 through 10. Case/whitespace-only differences create no request, and confirmation preserves canonical extracted spelling. The frontend year selector supports the same range. Frontend lowercase comparison is a preview; if the backend finds no actual difference after casefold, the UI accepts `change_request: null` as successful activation rather than displaying pending review.

Task 4.4 now backs the existing Student lock/pre-check with a unique virtual pending-owner column. This applies across screenings and includes legacy pending rows; terminal statuses release the slot automatically. Database creation conflicts map to the existing `409 CHANGE_REQUEST_PENDING`. Migration refuses ambiguous duplicate pending rows without choosing a decision. The derived column is not part of the Student payload/response and changes no activation or sign-in rule.

Task 4.5 adds session-only Student correction status reads: the shared list is SQL-scoped to the authenticated stable owner and supports status filters/pagination; an own request status-detail GET conceals other/missing IDs with the same 404. Responses separate current account/profile values, requested fields and the recorded baseline, with null for unknown legacy history. Reviewer IDs, file metadata, raw JSON and clinical content are excluded. Pending/expired Students can read their own account outcomes while existing feature restrictions remain. No Student request-rewrite or decision operation is added, and the frontend indicators remain Task 11.

## Reject account (ADR-033)

On the review or re-upload step a pre-active Student may cancel registration with **Reject account** (`POST /cor-screenings/reject-account`, Student session or `X-COR-Token`, `204`). It deletes the account and everything tied to it — the `users` row, its `cor_screenings`/`cor_screening_files`, `student_profiles`, `user_sessions`, any pending `profile_change_requests`, and the private COR bytes — and records a single `account_rejected` audit event. The email and student number become reusable for a fresh registration. Only `PENDING_VERIFICATION` accounts may self-cancel (a previously active account may own counseling history); other statuses return `409 ACCOUNT_NOT_REJECTABLE`. The legacy `POST /cor-screenings/reject` (mark `NEEDS_RESUBMISSION`/`REJECTED_BY_STUDENT`) is retired from the UI and kept only for compatibility.

## Implemented cleanup and concurrency

- The registration endpoint accepts `multipart/form-data` (`email`, `password`, `file`). The PDF/size limit is set by ADR-024 (10 MB default); uploads are read with a bounded size.
- Screening runs in-request. A submission locks the Student row, then the screening row, and re-reads current state. A competing confirmation receives `409 SCREENING_NOT_CONFIRMABLE`.
- The screening replacement and retired file metadata commit together; only then is the old file deleted. A new enrollment upload also releases any superseded versioned correction COR after commit. Confirmation likewise commits before deletion. Failed deletion preserves the file row as `FAILED` for retry, including replacement failures.
- The FastAPI lifespan starts a cleanup worker immediately and every 60 seconds while the application runs. It expires stale screenings, deletes due files, and retries failed deletion. Confirmation and resubmission independently deny expired evidence even between cleanup passes.
- An empty, UUID-named `.pending` marker in private storage tracks a write interrupted before DB commit. Abandoned marked uploads are reconciled after seven days; unrelated files are never swept. These markers contain no document content.
- Cleanup failures log only outcome codes/internal IDs. Monitor `cor_screening_cleanup_worker_failed`, `cor_screening_cleanup_retry_required`, and `cor_screening_file_cleanup_failed`; fix storage/database access failures so retries can succeed.
- For an application that is not continuously running, schedule `python -m app.modules.cor_screening.cleanup` from `backend/` against its configured private store and database. This command performs one cleanup pass. No deletion can run while every application/cleanup process is stopped.

## Authorization

- Student: register, view own screening (`GET /cor-screenings/me`), confirm (`POST /cor-screenings/confirm`), reject (`POST /cor-screenings/reject`), resubmit (`POST /cor-screenings/resubmit`). Confirm/reject/resubmit also accept the one-time `X-COR-Token` in place of a session (ADR-031); `GET /cor-screenings/me` stays session-only.
- Counselor: existing read-only screening list (`GET /cor-screenings`). No registration-correction review through Superadmin endpoints; counseling authority remains unchanged.
- Guidance Staff: no COR screening access under ADR-029.
- Pending/expired Student: own account and COR re-verification only.

## Required tests

Pending/expired access block; unauthorized read; malicious name/MIME/size; outcome matrix (format/extraction/missing/barcode); strict student-number rejection; no auto-created reference rows; missing-tooling fail-closed; resubmission replacement; confirmation activation + `valid_until` + deletion; seven-day cleanup/retry; barcode payload never persisted or logged. One-time token: register returns a hashed-only token; token confirm/reject/re-upload succeed with no session; invalid/expired/rotated tokens return `401 INVALID_VERIFICATION_TOKEN`; a present-but-invalid token never falls back to a valid session; the token is destroyed on activation.

## Pending

Accepted formats/size beyond ADR-024, authoritative registrar verification (residual spoofability), and exact student-facing wording for each failure code.
