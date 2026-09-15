# CounselConnect — Registration and Enrollment Verification

## Contract

Student registers with Student Number, personal email, required account/academic data, and **current COR only**. A new account is `PENDING_VERIFICATION` and has no normal Student access.

```text
validate input/file → pending account + private temporary COR
→ assigned Guidance Staff or Counselor review
→ APPROVED / NEEDS_RESUBMISSION / REJECTED
→ record decision + delete COR
```

If still pending after seven days: delete COR, set verification `EXPIRED`, and keep the account restricted. Approval sets account `ACTIVE` plus `valid_until`. When that date passes, set `VERIFICATION_EXPIRED`; Student may submit a new current COR to renew. Never infer graduation from year level.

## File controls

- Allowlist type/size; inspect signature/MIME; randomize storage key.
- Keep outside public/static paths; authorize every review fetch; never expose storage paths.
- Delete after every decision, replacement, or expiry. Record/retry/alert cleanup failure.
- Exclude temporary files from long-lived backups where feasible.
- MySQL keeps status, timestamps, reviewer/reason, `valid_until`, and cleanup metadata—not document bytes.

## Implemented cleanup and concurrency

- Both registration endpoints use `StudentRegistrationRequest` validation. The PDF/size limit is set by ADR-024 (10 MB default); uploads are read with a bounded size.
- Submissions and decisions lock the Student row, then the verification row, and re-read the current state. A competing decision receives `409 DECISION_ALREADY_MADE`.
- Pending replacements retain the original seven-day deadline. The replacement and retired file metadata commit together; only then is the old file deleted. Decisions likewise commit before deletion. Failed deletion preserves the file row as `FAILED` for retry, including replacement failures.
- The FastAPI lifespan starts a cleanup worker immediately and every 60 seconds while the application runs. It expires pending verifications, deletes due files, and retries failed deletion. Preview and decision paths independently deny expired evidence, even between cleanup passes.
- An empty, UUID-named `.pending` marker in private storage tracks a write interrupted before DB commit. Abandoned marked uploads are reconciled after seven days; unrelated files are never swept. These markers contain no document content.
- Cleanup failures log only outcome codes/internal IDs. Monitor `verification_cleanup_worker_failed`, `verification_cleanup_retry_required`, and `verification_file_cleanup_failed`; fix storage/database access failures so retries can succeed.
- For an application that is not continuously running, schedule `python -m app.modules.enrollment_verification.cleanup` from `backend/` against its configured private store and database. This command performs one cleanup pass. No deletion can run while every application/cleanup process is stopped.

## Authorization

- Guidance Staff: assigned cases only; the pending queue, history, COR preview, and decision actions are scoped to `assigned_guidance_staff_user_id`.
- Counselor: authorized queue, decisions, permitted academic corrections, and assignment of a pending case to an active Guidance Staff member.
- Pending/expired Student: own account and COR re-verification only.

## Required tests

Pending/expired access block; unauthorized/cross-assignment read; malicious name/MIME/size; each state transition; delete/retry; seven-day cleanup; renewal/`valid_until`; no public/direct path.

## Pending

Accepted formats/size, exact rejection/appeal/privacy wording, and audit field set.
