# CounselConnect — Security and Privacy

## Shared controls

- Authenticate protected endpoints; enforce role, assignment, ownership, appointment mode/status/time, and conversation-purpose authorization server-side.
- Least-privilege app/DB/storage credentials; externalized secrets; safe SQLAlchemy queries and controlled Alembic migrations.
- Validate/sanitize inputs, uploads, CMS data, URLs, redirects, and external metadata.
- Keep confidential data out of routine logs, errors, URLs, analytics, and unapproved services.
- Audit high-impact decisions/outcomes with minimal metadata; do not copy sensitive content into audit records.

## Login sessions (ADR-019 — implemented)

Web authentication uses opaque sessions in the HttpOnly `counselconnect_session` cookie. `user_sessions` stores only SHA-256 digests (BINARY(32)) of a ≥256-bit random credential and its session-bound CSRF token; raw credentials are never stored, logged, or returned in response bodies (the CSRF token itself IS returned to the authenticated caller by login/refresh, and must be echoed in the `X-CSRF-Token` header on unsafe methods). Students sign in with their registered email or student number; staff with email (ADR-030). Passwords hash with Argon2id; legacy bcrypt hashes verify and upgrade transparently on successful login.

- Sessions idle-expire after one hour without genuine user activity (computed from `last_activity_at`) and absolutely expire 12 hours after creation; the absolute window never slides or extends. Login and refresh return both expiry timestamps for the frontend's five-minute idle warning.
- Only genuine CounselConnect user actions update `last_activity_at`. Background polling, WebSocket ping/pong, connection heartbeats, and open background tabs must not renew authentication.
- Revoked, idle-expired, and absolute-expired sessions fail authentication; a new login revokes the user's other live sessions (single-session policy).
- Logout, password reset, account restriction, and account disablement must revoke sessions (one or all for the user).
- The table stores no IP history, device fingerprints, COR data, message content, or SOS answers.
- Staff email lookup takes precedence over colliding student numbers; new registrations reject collisions with existing staff identifiers. Students at every account status sign in with their registered email or student number (ADR-030).
- `/auth/csrf` restores both user and CSRF state before protected UI mounts. CSRF is derived with domain-separated HMAC from the random session credential, so recovery does not invalidate other tabs; only its SHA-256 digest is stored. Legacy random CSRF tokens migrate on recovery. `/auth/me` and `/auth/csrf` do not renew idle activity. Auth responses use `Cache-Control: no-store`. `/auth/csrf` returns `null` (200) when the caller holds no live session, so the anonymous startup probe is not reported as a 401; authenticated callers still receive the full `AuthResponse`.
- Login is allowed for `ACTIVE`, `PENDING_VERIFICATION`, and `VERIFICATION_EXPIRED` accounts (pending/expired students must still reach account/COR re-verification); feature-level authorization still requires `ACTIVE` where the feature docs say so.
- Password-reset credentials will be hashed, single-use, 30-minute expiry, and a successful reset revokes all active sessions without revealing account existence (flow in its own task; no Remember Me in v1).

## One-time COR verification token (ADR-031 — implemented)

Registration no longer signs the Student in. `POST /accounts/register/student-with-cor` and `POST /cor-screenings/resubmit` return a single-use `verification_token`; the client keeps it in memory and sends it in the `X-COR-Token` header to authorize `confirm`, `reject`, and `resubmit` for that screening only.

- The token is a 256-bit random value (`secrets.token_urlsafe(32)`); only its SHA-256 digest is stored (`cor_screenings.verification_token_hash BINARY(32)` plus `verification_token_issued_at`). Verification uses a constant-time digest compare. Raw tokens are never persisted, logged, or placed in URLs or error messages.
- It shares the seven-day evidence window and is rotated on every re-upload, destroyed on activation (`PASSED`), and destroyed when the screening reaches `FAILED` at expiry (both on resolve and in the cleanup worker). An expired token also retires its screening.
- Missing, unknown, tampered, expired, or rotated-away tokens fail closed with `401 INVALID_VERIFICATION_TOKEN` and a generic message. A present-but-invalid token never falls back to session authentication.
- Token-authorized requests are cookie-less, so CSRF does not apply to them; session-authenticated requests keep the existing CSRF rule. Token-bearing responses are `Cache-Control: no-store`.
- Residual: closing the registration modal before acting loses the token by design (it is memory-only); the Student recovers through the signed-in `#registration` session path.

## Registration correction review

**Existing implementation:** ADR-032 activates the Student with extracted values and stores a separate pending names/year_level/section proposal. Active Superadmins alone list and approve/reject requests. Task 4.3 retains the exact pending-correction COR within its original seven-day deadline. Existing approve/reject now commit decision/audit before invoking cleanup; complete review evidence/version/staleness checks remain later work.

**Task 4.2 implemented:** New changed submissions store separate immutable structured extraction and registered-baseline snapshots, version-1 metadata, and the exact evidence ID/digest/timestamps. Ownership is tied to the resolved account and screening; unavailable metadata fails explicitly before activation. Existing response DTOs exclude this internal context. Submission auditing now commits with activation/request and contains only safe status/version/actor/target/time metadata. Audit failure rolls back these changes and preserves the file. No legacy context is inferred. Task 4.3 adds bounded pending-review retention, system return on expiry/unavailable metadata, safe audited cleanup retries, and cleanup after committed decisions/replacement. Approval independently rejects expired captured deadlines before the worker runs; byte integrity, stale baseline and submission-version hardening remain Task 6.

**Task 4.4 implemented:** A MySQL unique virtual pending-owner guard backs the existing Student lock/pre-check for every pending row, including legacy contexts. It derives stable account ID from status; clients cannot clear it to bypass uniqueness, and terminal states release it automatically. Guard conflicts roll back and return safe `CHANGE_REQUEST_PENDING` without SQL or proposed values. Migration preflight refuses duplicate existing requests without auto-deciding them; no account or clinical data changes. The derived field is excluded from DTOs.

**Task 4.5 implemented:** Session-authenticated Students can list/read only their own correction status. SQL owner filtering applies to both list counts/pages and detail lookup; another owner's ID is concealed as the same not-found response. A separate Student DTO omits operational reviewer IDs and private evidence fields, projects only the five supported baseline fields, and leaves unknown legacy history null. Current registered values are read from account/profile, with no fallback to a proposal. Successful responses are `no-store` and UTC `Z`; COR tokens alone do not authorize reads. Pending/expired account reads do not unlock normal services, and a deactivated Student is denied even with a live cookie. No clinical tables or general audit history are read. Existing Student read permission grants no decision or request-edit operation.

**AGREED target, not implemented:** [REGISTRATION_CORRECTIONS.md](REGISTRATION_CORRECTIONS.md) owns the extended contract: immutable extraction/baseline/evidence metadata, versioned returns/resubmission, own-Student reads, Superadmin-only private COR reads, stale/concurrent review protection, and atomic audit/decision/profile changes. The user approved retaining an exact pending-correction COR only until approval/return/replacement or its original seven-day upload deadline. Expiry returns the correction without changing enrollment eligibility. Missing or expired evidence blocks approval; raw PDFs, paths, tokens, proposed values, and return text never enter general logs/notifications. Historical unknown snapshots remain unknown.

## Users Management backend

**Counselor account extension (2026-10-26):** Active non-deactivated Superadmins may create server-fixed COUNSELOR/ACTIVE/enabled accounts with Superadmin-entered initial passwords, and edit only Counselor names/email with the displayed timezone-aware updated timestamp. Existing Argon2id, CSRF, no-store responses, strict allowlists, protected targets and fresh actor/target locks apply. Email changes atomically revoke all sessions; login rechecks the resolved email after acquiring its User lock. Name-only edits preserve sessions; password/status/role and clinical/scheduling relationships remain unchanged. Passwords are request/form-only, never returned/audited/emailed. No password reset or automatic credential delivery is added. Atomic audits contain only safe fixed state/changed field names and a revocation boolean. See the owning Users contract for exact input and conflict rules.

**Implemented:** Active non-deactivated Superadmins can read only safe account/current enrollment summaries and deactivate/reactivate Students/Counselors. Superadmin/Guidance Staff targets are protected. Deactivation, ACCOUNT_DISABLED session revocation and safe flag audit are atomic/idempotent; failed writes roll back. Reactivation does not change enrollment or restore sessions. Login/session issuance and status operations serialize on the target User; current HTTP and COR-token/recovery checks enforce the flag. Authentication/activity locks finish before domain participant locks. Socket revalidation uses fresh read-only sessions without renewing idle activity; calls recheck before signaling, and notification sockets recheck by elapsed time even while busy. Private Users responses/errors are no-store and omit untrusted validation input, credentials, session/COR metadata and clinical data. No invitations, role edits, hard deletion or automatic appointment/clinical mutations were added. Existing schema downgrade still refuses to discard a true flag. See the owning contract for exact projections and endpoints.

## Registration failure isolation and cancellation (ADR-033 — implemented)

A **technical** screening failure during registration (`derive_outcome == FAILED`) creates no account: the COR is discarded and the API returns `503 SCREENING_FAILED`, leaving the email/student number free. A `PENDING_VERIFICATION` Student may also cancel their own registration with `POST /cor-screenings/reject-account` (Student session or `X-COR-Token`): it deletes the user row, its screenings and private COR files, sessions, profile, and any pending profile-edit requests, frees the email/student number, and records one `account_rejected` audit event. Any other status (including a previously active account that may own counseling history) returns `409 ACCOUNT_NOT_REJECTABLE`.

## Sensitive data matrix

| Data | Storage/retention | Key restriction |
|---|---|---|
| Login sessions | digest-only rows; deleted when expired/revoked or user deleted | no raw credentials in storage/logs/API; heartbeats never renew activity |
| COR verification token | SHA-256 digest only on `cor_screenings`; expires with the 7-day window; destroyed on activation/TTL | returned once in the register/resubmit body; set `X-COR-Token`; never logged or in URLs; `no-store` |
| Registration correction | Existing requested fields/decision; target adds immutable structured context and versions | Own-Student reads; Superadmin review only; no clinical access; no sensitive generic notifications; see owning contract |
| Registration cancellation | deleted on Student request (pre-active only); email/student number freed | non-active only; audited `account_rejected`; private COR bytes removed |
| Current COR | private temporary store; target pending-correction exception ends at decision/replacement or original seven-day deadline | no MySQL blob/public URL/backups beyond need; exact pending evidence only; see owning contract |
| Appointments | authorized durable records | owner/Counselor scope; mode compatibility; Counselor-only campus-location mutation |
| Messages | authorized store; bodies purged 30 days after close | no recordings/transcripts/summaries/log bodies |
| SOS | approved fields; retention pending | Counselor scope; no diagnostic claim |
| Expression cue | active session only | no raw media/embedding/history; no SOS influence |
| External resources | bounded metadata/canonical URL | allowlist, SSRF/redirect controls, Counselor review |
| Internal resource files | controlled durable store | authorized retrieval, file validation |
| CMS/contacts | structured durable records | Counselor-only mutation; sanitized rendering |

## Appointment-linked messaging controls

- Create an `APPOINTMENT` conversation only for a confirmed online appointment when its scheduled start is reached, subject to any later approved pre-start window.
- Revalidate appointment ownership, assigned Counselor, selected mode, status, and scheduled time on open and reconnect.
- Require the appointment and conversation to contain the same Student and Counselor.
- Deny appointment-conversation creation for face-to-face, pending, rejected, cancelled, completed, or unauthorized appointments.
- Enforce the one-to-one appointment/conversation link and prevent appointment/SOS dual linkage.
- Treat the stored face-to-face `meeting_location` as an appointment snapshot; only Counselor may change the source campus Guidance Office location.

File deletion is outside a DB rollback: persist cleanup state, detect failure, retry/alert, and never falsely report deletion. Data-minimizing architecture supports privacy compliance but does not alone prove legal compliance; deployed notices, lawful purpose, safeguards, retention, and disposal still matter.

Existing COR confirmation/resubmission commits before deletion; the agreed target pending-correction exception is defined in `REGISTRATION_CORRECTIONS.md`. Failed deletions retain `cleanup_state=FAILED` metadata for the application cleanup worker; logs contain only outcome codes and internal record IDs. Raw OCR text and raw barcode payloads are never persisted or logged (payload SHA-256 digest only). See `REGISTRATION_VERIFICATION.md` for expiry and retry operation.

Validation errors return only field locations, error types, and safe messages. Submitted inputs, passwords, and validator context are excluded. Database tests require a separate explicit test URL, use a unique disposable schema, and override application database access; their file stores and SMTP settings are isolated as well.

## Priority tests

Horizontal/vertical authorization; pending/expired account block; Staff assignment isolation; malicious upload/direct path; cleanup failure/TTL; appointment/message ownership; appointment mode/slot compatibility; missing campus-location denial; Counselor-only campus-location mutation; pre-start/unconfirmed/cancelled online-chat denial; participant mismatch; face-to-face conversation denial; appointment/SOS link isolation; CMS injection; SSRF/unsafe redirect; raw-media network/storage prevention; SOS independence from cue; one-time COR token fail-closed (invalid/empty/expired/rotated, no session fallback, digest-only, destroyed on activation); profile-edit approval (Superadmin-only, excluded fields rejected, one-pending, supersede); registration failure isolation (no account on technical FAILED) and self-cancellation (deletes all rows/files, frees identity, audited); sensitive-log review.
