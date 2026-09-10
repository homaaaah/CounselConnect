# CounselConnect — Durable Decisions

Status values: `APPROVED`, `PENDING`, `SUPERSEDED`.

## Approved

| ID | Decision |
|---|---|
| ADR-001 | React + Vite + TailwindCSS; FastAPI; CapacitorJS; modular monolith. |
| ADR-002 | MySQL 8.4 LTS with SQLAlchemy 2.0, PyMySQL, and Alembic. |
| ADR-003 | Roles are `STUDENT`, `GUIDANCE_STAFF`, `COUNSELOR`; no Administrator. Counselor is highest authority. Guidance Staff is limited to assigned COR verification. |
| ADR-004 | Current COR is the only registration/renewal evidence. Store privately outside MySQL; delete after decision or seven-day pending TTL. |
| ADR-005 | Students sign in with Student Number; registration also collects personal email. Initial staff accounts are developer-created; Counselor may manage authorized accounts/Guidance Staff later. |
| ADR-006 | Approved verification sets account `ACTIVE` and `valid_until`; expired validity locks normal features without inferring graduation from year level. |
| ADR-007 | Appointments use concrete slots, Student `PENDING` requests, and Counselor decisions. No recurrence/history table in v1. |
| ADR-008 | One Student ↔ one Counselor per conversation. Message bodies remain 30 days after closure, then are purged; minimal metadata may remain. No recordings/transcripts/summaries. |
| ADR-009 | Optional facial-expression inference is local-device, about three seconds, session-only, non-diagnostic, and never affects SOS. No raw media, embeddings, or history. |
| ADR-010 | SOS uses five approved questions and rule-based logic only; cases use `OPEN`, `RESPONDED`, `CLOSED`. |
| ADR-011 | Automated resource discovery uses allowlisted RSS/Atom/structured metadata first and approved limited scraping fallback; Counselor review precedes publication; no mirrored full articles. |
| ADR-012 | Manual resources may be external links, internal articles, or controlled files with multiple attachments/categories. |
| ADR-013 | Assistant uses approved navigation/FAQ content and `PUBLISHED` resources only; no diagnosis, policy invention, confidential external disclosure, or persistent history. |
| ADR-014 | Counselor owns designated CMS, announcements, emergency contacts, user/staff management, academic corrections, and authorized audit views. Basic content is current immediately; announcements publish/unpublish manually. No drafts/versioning/scheduling. |
| ADR-015 | Persist/API timestamps in UTC and display in `Asia/Manila`. |
| ADR-016 | Keep agent context routed and compact; `.ai/NAMING_CONVENTIONS.md` is authoritative for identifiers. |
| ADR-017 | Concrete availability slots support `ONLINE`, `FACE_TO_FACE`, or `BOTH`. Counselor alone manages each campus Guidance Office location. A campus without a configured location cannot offer `FACE_TO_FACE` or `BOTH`. A face-to-face appointment stores the campus location as a booking-time snapshot. |
| ADR-018 | A confirmed online appointment may create exactly one dedicated `APPOINTMENT` conversation when its scheduled start is reached. The Student and Counselor must match the appointment. `GENERAL`, `APPOINTMENT`, and `SOS` conversations remain separate, and face-to-face appointments cannot link a conversation. |
| ADR-019 | Authentication (approved 2026-09-05, formerly pending ADR-P01): Students sign in with student number; staff sign in with email. Passwords hash with Argon2id (existing bcrypt hashes verified and upgraded on next successful login). Web auth uses revocable MySQL-backed opaque sessions in a secure HttpOnly `counselconnect_session` cookie (256-bit random credential, SHA-256-stored) with a session-bound CSRF token (SHA-256-stored; `X-CSRF-Token` header on unsafe methods). Sessions idle-expire after one hour of no genuine user activity and absolutely expire 12 hours after creation with no sliding; background polls/heartbeats never renew activity. Login is allowed for `PENDING_VERIFICATION`, `ACTIVE`, and `VERIFICATION_EXPIRED` accounts (pending/expired students reach only account and re-verification functions); feature-level authorization still requires `ACTIVE` and valid enrollment where the docs say so. Password-reset credentials are hashed, single-use, expire in 30 minutes, and a successful reset revokes all active sessions without revealing account existence (flow implemented in its own task). No Remember Me in v1. |

## Pending

| ID | Decision needed |
|---|---|
| ADR-P02 | Real-time messaging transport/delivery semantics. |
| ADR-P03 | Exact SOS instrument, rule thresholds, availability/fallback rule, and SOS retention. |
| ADR-P04 | Appointment duration/buffer, cancellation/reschedule cutoffs, reminders, and blocked-period policy. |
| ADR-P05 | COR file types/size, rejection/appeal wording, privacy notice, and exact audit fields. |
| ADR-P06 | Production local expression library/model, label set, confidence/UX behavior, and supported devices. |
| ADR-P07 | Manual-resource publication/review rule and attachment limits. |
| ADR-P08 | Assistant model/provider and bounded retrieval implementation. |
| ADR-P09 | Capacitor session-credential transport and production password-reset email delivery/fallback. |

Do not convert a pending item into code policy without human approval.
