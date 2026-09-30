# CounselConnect — Registration and Enrollment Verification

## Contract

Student registers with personal email, password, and the **current COR only** (ADR-029). The COR is the source of truth for the academic fields. A new account is `PENDING_VERIFICATION` and has no normal Student access.

```text
validate credentials + COR PDF
→ automate screening (format score + OCR extraction + embedded barcode)
→ AWAITING_CONFIRMATION  (clean screening)
   or NEEDS_RESUBMISSION (unreadable / low score / missing / barcode failure)
→ Student confirms or corrects the extracted fields
→ account ACTIVE + valid_until, screening PASSED, COR deleted
```

The confirmation step appears **inline on the registration form** (prototype-style): on a successful submission the client establishes the session with the just-registered credentials, then renders the extracted fields for review and confirmation in the same card — no separate sign-in detour. If the screening needs resubmission, the same card links to the re-upload step.

There is no human approval queue. A screening is `AWAITING_CONFIRMATION` only when the format score and extraction confidence meet the configured thresholds **and** the embedded barcode decodes and matches the extracted student number. Anything less is `NEEDS_RESUBMISSION` and the Student re-uploads. If the screening tooling is unavailable, registration fails closed (`SCREENING_UNAVAILABLE`) and never activates an account.

Students sign in with their registration email or their student number (ADR-019/ADR-030).

The confirming Student must supply a strict UCC student number (`^\d{8}-[A-Za-z]$`, e.g. `20231234-A`) and select a campus/program that already exists as an active reference row. **All verified academic fields are read-only** during confirmation — student number, names, year level, section, academic year, and any campus/program the COR was mapped to. The Student either **confirms** or **rejects** the result; rejecting sets `NEEDS_RESUBMISSION` / `REJECTED_BY_STUDENT`, offers a re-upload, and signs the Student out. The backend rejects a request that changes any verified field (`FIELD_MISMATCH`) or the student number (`STUDENT_NUMBER_MISMATCH`), so a crafted request cannot rewrite verified data. Only a campus/program the COR could not be mapped to stays selectable. Extracted names are never used to create campuses or programs.

`AWAITING_CONFIRMATION` requires every required field (student number, name, course/program, year, section) to be present, plus a format score and extraction confidence at or above the thresholds, and a decoded barcode consistent with the extracted student number. The barcode's academic-period value is cross-checked against OCR when both are present, and the decode result/confidence is recorded. `valid_until` uses the enrollment-validity date read from the COR when it is still in the future, otherwise a 12-month default.

If an open screening is still pending after seven days: the screening becomes `FAILED`, the COR is deleted, and the account stays `PENDING_VERIFICATION`. Approval sets account `ACTIVE` plus `valid_until`; when that date passes, set `VERIFICATION_EXPIRED`; the Student may submit a new current COR to renew. Never infer graduation from year level.

## File controls

- Allowlist type/size; inspect signature/MIME; randomize storage key.
- Keep outside public/static paths; authorize every read; never expose storage paths.
- Delete after confirmation, replacement, or expiry. Record/retry/alert cleanup failure.
- Exclude temporary files from long-lived backups where feasible.
- MySQL keeps screening status, scores, extracted fields, `valid_until`, and cleanup metadata—not document bytes. Raw OCR text and raw barcode payloads are never stored or logged; only a SHA-256 digest of the barcode payload.

## Screening statuses and failure codes

- Statuses: `PROCESSING`, `AWAITING_CONFIRMATION`, `PASSED`, `NEEDS_RESUBMISSION`, `FAILED`. The record is committed as `PROCESSING` before it is resolved (ADR-030).
- Barcode statuses: `NOT_PROCESSED`, `NOT_FOUND`, `UNREADABLE`, `INVALID_FORMAT`, `DECODED`, `MISMATCH`.
- Failure codes: `UNREADABLE_DOCUMENT`, `LOW_FORMAT_SCORE`, `MISSING_REQUIRED_FIELDS`, `LOW_EXTRACTION_CONFIDENCE`, `BARCODE_*`, `TECHNICAL_ERROR` (→ `FAILED`), `FIELD_MAPPING_FAILED`, `REJECTED_BY_STUDENT`, `ADMIN_RECOVERY`.
- Confirmation codes: `STUDENT_NUMBER_MISMATCH` (number differs from the screened value) and `FIELD_MISMATCH` (any verified field differs).

## Implemented cleanup and concurrency

- The registration endpoint accepts `multipart/form-data` (`email`, `password`, `file`). The PDF/size limit is set by ADR-024 (10 MB default); uploads are read with a bounded size.
- Screening runs in-request. A submission locks the Student row, then the screening row, and re-reads current state. A competing confirmation receives `409 SCREENING_NOT_CONFIRMABLE`.
- The screening replacement and retired file metadata commit together; only then is the old file deleted. Confirmation likewise commits before deletion. Failed deletion preserves the file row as `FAILED` for retry, including replacement failures.
- The FastAPI lifespan starts a cleanup worker immediately and every 60 seconds while the application runs. It expires stale screenings, deletes due files, and retries failed deletion. Confirmation and resubmission independently deny expired evidence even between cleanup passes.
- An empty, UUID-named `.pending` marker in private storage tracks a write interrupted before DB commit. Abandoned marked uploads are reconciled after seven days; unrelated files are never swept. These markers contain no document content.
- Cleanup failures log only outcome codes/internal IDs. Monitor `cor_screening_cleanup_worker_failed`, `cor_screening_cleanup_retry_required`, and `cor_screening_file_cleanup_failed`; fix storage/database access failures so retries can succeed.
- For an application that is not continuously running, schedule `python -m app.modules.cor_screening.cleanup` from `backend/` against its configured private store and database. This command performs one cleanup pass. No deletion can run while every application/cleanup process is stopped.

## Authorization

- Student: register, view own screening (`GET /cor-screenings/me`), confirm (`POST /cor-screenings/confirm`), reject (`POST /cor-screenings/reject`), resubmit (`POST /cor-screenings/resubmit`).
- Counselor: read-only screening/audit list (`GET /cor-screenings`). No approval/edit action; the Counselor authority remains for account/academic corrections.
- Guidance Staff: no COR screening access under ADR-029.
- Pending/expired Student: own account and COR re-verification only.

## Required tests

Pending/expired access block; unauthorized read; malicious name/MIME/size; outcome matrix (format/extraction/missing/barcode); strict student-number rejection; no auto-created reference rows; missing-tooling fail-closed; resubmission replacement; confirmation activation + `valid_until` + deletion; seven-day cleanup/retry; barcode payload never persisted or logged.

## Pending

Accepted formats/size beyond ADR-024, authoritative registrar verification (residual spoofability), and exact student-facing wording for each failure code.
