# CounselConnect — Security and Privacy

## Shared controls

- Authenticate protected endpoints; enforce role, assignment, ownership, appointment mode/status/time, and conversation-purpose authorization server-side.
- Least-privilege app/DB/storage credentials; externalized secrets; safe SQLAlchemy queries and controlled Alembic migrations.
- Validate/sanitize inputs, uploads, CMS data, URLs, redirects, and external metadata.
- Keep confidential data out of routine logs, errors, URLs, analytics, and unapproved services.
- Audit high-impact decisions/outcomes with minimal metadata; do not copy sensitive content into audit records.

## Sensitive data matrix

| Data | Storage/retention | Key restriction |
|---|---|---|
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

## Priority tests

Horizontal/vertical authorization; pending/expired account block; Staff assignment isolation; malicious upload/direct path; cleanup failure/TTL; appointment/message ownership; appointment mode/slot compatibility; missing campus-location denial; Counselor-only campus-location mutation; pre-start/unconfirmed/cancelled online-chat denial; participant mismatch; face-to-face conversation denial; appointment/SOS link isolation; CMS injection; SSRF/unsafe redirect; raw-media network/storage prevention; SOS independence from cue; sensitive-log review.
