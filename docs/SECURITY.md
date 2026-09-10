# CounselConnect — Security and Privacy

## Shared controls

- Authenticate protected endpoints; enforce role, assignment, ownership, appointment mode/status/time, and conversation-purpose authorization server-side.
- Least-privilege app/DB/storage credentials; externalized secrets; safe SQLAlchemy queries and controlled Alembic migrations.
- Validate/sanitize inputs, uploads, CMS data, URLs, redirects, and external metadata.
- Keep confidential data out of routine logs, errors, URLs, analytics, and unapproved services.
- Audit high-impact decisions/outcomes with minimal metadata; do not copy sensitive content into audit records.

## Login sessions (ADR-019 — implemented)

Web authentication uses opaque sessions in the HttpOnly `counselconnect_session` cookie. `user_sessions` stores only SHA-256 digests (BINARY(32)) of a ≥256-bit random credential and its session-bound CSRF token; raw credentials are never stored, logged, or returned in response bodies (the CSRF token itself IS returned to the authenticated caller by login/refresh, and must be echoed in the `X-CSRF-Token` header on unsafe methods). Students sign in with their student number; staff with email. Passwords hash with Argon2id; legacy bcrypt hashes verify and upgrade transparently on successful login.

- Sessions idle-expire after one hour without genuine user activity (computed from `last_activity_at`) and absolutely expire 12 hours after creation; the absolute window never slides or extends. Login and refresh return both expiry timestamps for the frontend's five-minute idle warning.
- Only genuine CounselConnect user actions update `last_activity_at`. Background polling, WebSocket ping/pong, connection heartbeats, and open background tabs must not renew authentication.
- Revoked, idle-expired, and absolute-expired sessions fail authentication; a new login revokes the user's other live sessions (single-session policy).
- Logout, password reset, account restriction, and account disablement must revoke sessions (one or all for the user).
- The table stores no IP history, device fingerprints, COR data, message content, or SOS answers.
- Staff email lookup takes precedence over colliding student numbers; new registrations reject collisions with existing staff identifiers. Students use their student number, not their personal email, to sign in.
- `/auth/csrf` restores both user and CSRF state before the reviewer UI mounts. CSRF is derived with domain-separated HMAC from the random session credential, so recovery does not invalidate other tabs; only its SHA-256 digest is stored. Legacy random CSRF tokens migrate on recovery. `/auth/me` and `/auth/csrf` do not renew idle activity. Auth responses use `Cache-Control: no-store`.
- Login is allowed for `ACTIVE`, `PENDING_VERIFICATION`, and `VERIFICATION_EXPIRED` accounts (pending/expired students must still reach account/COR re-verification); feature-level authorization still requires `ACTIVE` where the feature docs say so.
- Password-reset credentials will be hashed, single-use, 30-minute expiry, and a successful reset revokes all active sessions without revealing account existence (flow in its own task; no Remember Me in v1).

## Sensitive data matrix

| Data | Storage/retention | Key restriction |
|---|---|---|
| Login sessions | digest-only rows; deleted when expired/revoked or user deleted | no raw credentials in storage/logs/API; heartbeats never renew activity |
| Current COR | private temporary store; decision or seven-day TTL | no MySQL blob/public URL/backups beyond need |
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

COR decisions commit before deletion. Failed deletions retain `cleanup_state=FAILED` metadata for the application cleanup worker; logs contain only outcome codes and internal record IDs. Private PDF responses use `Cache-Control: no-store`; the reviewer releases preview blob URLs after decisions and on unmount. See `REGISTRATION_VERIFICATION.md` for expiry and retry operation.

Validation errors return only field locations, error types, and safe messages. Submitted inputs, passwords, and validator context are excluded. Database tests require a separate explicit test URL, use a unique disposable schema, and override application database access; their file stores and SMTP settings are isolated as well.

## Priority tests

Horizontal/vertical authorization; pending/expired account block; Staff assignment isolation; malicious upload/direct path; cleanup failure/TTL; appointment/message ownership; appointment mode/slot compatibility; missing campus-location denial; Counselor-only campus-location mutation; pre-start/unconfirmed/cancelled online-chat denial; participant mismatch; face-to-face conversation denial; appointment/SOS link isolation; CMS injection; SSRF/unsafe redirect; raw-media network/storage prevention; SOS independence from cue; sensitive-log review.
