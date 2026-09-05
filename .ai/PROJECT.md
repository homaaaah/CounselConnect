# CounselConnect — Naming Conventions

Authoritative for new APIs, schemas, database objects, events, and source files. Preserve existing diagram/ERD names unless a migration intentionally changes them.

## Canonical domain language

| Display term | Code value / identifier |
|---|---|
| Student | `STUDENT`, `student` |
| Guidance Staff | `GUIDANCE_STAFF`, `guidance_staff` |
| Guidance Counselor / Counselor | `COUNSELOR`, `counselor` |
| Authenticated user session | `user_sessions`, `session` |
| Counselor SOS availability | `AVAILABLE`, `BUSY`, `UNAVAILABLE` |
| Certificate of Registration | `COR`, `cor` |
| Guidance Office location | `guidance_office_location` |
| Availability delivery mode | `delivery_mode` |
| Appointment mode | `appointment_mode` |
| Meeting-location snapshot | `meeting_location` |
| Conversation type | `conversation_type` |
| Observed Expression Cue | `observed_expression_cue` |
| SOS | `SOS`, `sos` |

Never introduce `ADMIN`, `administrator`, `student_id` evidence, `emotional_baseline` persistence, or identity/face-recognition terms. “Observed Expression Cue” is session context, not a stored student trait.

## Case by layer

| Layer | Convention | Example |
|---|---|---|
| Python files/functions/variables | `snake_case` | `enrollment_verification.py`, `approve_verification` |
| Python/TypeScript types, React components | `PascalCase` | `EnrollmentVerificationResponse`, `SOSCaseCard` |
| React hooks | `useCamelCase` | `useAppointmentSlots` |
| TS/JS variables/functions/props | `camelCase` | `verificationStatus` |
| Constants/enum values/error codes | `SCREAMING_SNAKE_CASE` | `NEEDS_RESUBMISSION`, `SLOT_UNAVAILABLE` |
| Database/API JSON/query fields | `snake_case` | `student_user_id`, `valid_until` |
| Database tables | plural `snake_case` | `enrollment_verifications` |
| URL resource segments | plural `kebab-case` | `/enrollment-verifications` |
| Environment variables | `COUNSELCONNECT_` + uppercase | `COUNSELCONNECT_DATABASE_URL` |
| Tests | mirror target + `_test`/`.test` | `test_appointments.py`, `AppointmentCard.test.tsx` |

Keep API DTO fields exactly `snake_case` in frontend API types; use `camelCase` only inside UI logic. Do not add silent global case conversion.

## Database

- Table: plural noun; PK: singular entity + `_id` (`users.user_id`, `appointments.appointment_id`).
- FK: referenced role/entity + `_id` (`student_user_id`, `reviewed_by_user_id`). Add role qualifiers when one table references `users` more than once.
- Boolean: `is_`, `has_`, or `can_`; timestamp: `_at`; calendar date: established domain name such as `valid_until`.
- Use created/updated timestamps only when needed. Store timestamps in UTC.
- Use `user_sessions` for revocable authentication sessions, with `session_id`, `token_hash`, `csrf_token_hash` when server-held, `last_activity_at`, `absolute_expires_at`, and `revoked_at`. Never name or store a raw session token as an identifier.
- Junction table combines plural entities; composite FKs form the PK (`wellness_resource_categories`).
- Status columns are `status`; specialized outputs use explicit names (`urgency_result_code`, `cleanup_state`).
- Use `delivery_mode` for a slot's supported delivery capability and `appointment_mode` for the Student's selected mode.
- Use `guidance_office_location` for the Counselor-managed campus value and `meeting_location` for the immutable face-to-face appointment snapshot.
- Use `conversation_type` to distinguish `GENERAL`, `APPOINTMENT`, and `SOS`; do not overload conversation `status` for purpose.
- JSON columns end `_json`; byte counts end `_bytes`; ordered UI fields use `display_order`.
- Do not prefix every column with its table name. Do not store COR blobs, expression cues, raw facial media, or assistant history.

The v1 table names in `docs/DATABASE.md` are canonical.

## HTTP API

- Base path: `/api/v1`.
- Use plural noun resources and standard verbs: `GET` read, `POST` create/transition, `PATCH` partial update, `DELETE` removal.
- Use `{entity_id}` path variables: `/appointments/{appointment_id}`.
- Nest only for ownership/context: `/conversations/{conversation_id}/messages`.
- Query parameters are `snake_case`: `?status=PENDING&page=1&page_size=20`.
- State transitions may use explicit action endpoints when a plain CRUD update would hide business rules:
  - `POST /enrollment-verifications/{verification_id}/approve`
  - `POST /enrollment-verifications/{verification_id}/request-resubmission`
  - `POST /appointments/{appointment_id}/confirm`
  - `POST /sos-cases/{sos_case_id}/close`
  - `POST /wellness-resources/{resource_id}/publish`
- Auth action exceptions use `/auth/login`, `/auth/logout`, `/auth/session`, and explicit password-recovery actions. Do not add `/auth/refresh` unless a future approved token design requires it.
- Never use role-specific duplicate routes when authorization can govern one resource route.

## Payloads and errors

- Schema names: `{Entity}CreateRequest`, `{Entity}UpdateRequest`, `{Entity}Response`, `{Entity}ListResponse`.
- Return a single resource directly. Lists use `{ "items": [], "page": 1, "page_size": 20, "total": 0 }`.
- Errors use `{ "error": { "code": "SLOT_UNAVAILABLE", "message": "...", "details": {} } }`; codes are stable, messages are human-readable, details contain no secrets.
- UTC timestamps use ISO 8601 with `Z`; dates use `YYYY-MM-DD`; API enums use uppercase code values.
- File uploads use `multipart/form-data`; metadata fields retain canonical `snake_case` names.

## Approved states and values

| Domain | Values |
|---|---|
| Account | `PENDING_VERIFICATION`, `ACTIVE`, `VERIFICATION_EXPIRED` |
| Counselor SOS availability | `AVAILABLE`, `BUSY`, `UNAVAILABLE` |
| Verification | `PENDING`, `APPROVED`, `NEEDS_RESUBMISSION`, `REJECTED`, `EXPIRED` |
| Availability status | `AVAILABLE`, `RESERVED` |
| Availability delivery mode | `ONLINE`, `FACE_TO_FACE`, `BOTH` |
| Appointment mode | `ONLINE`, `FACE_TO_FACE` |
| Appointment | `PENDING`, `CONFIRMED`, `COMPLETED`, `CANCELLED`, `REJECTED`, `NO_SHOW` |
| Conversation type | `GENERAL`, `APPOINTMENT`, `SOS` |
| Conversation status | `OPEN`, `CLOSED` |
| SOS case | `OPEN`, `RESPONDED`, `CLOSED` |
| Wellness resource | `PENDING`, `PUBLISHED`, `REJECTED`, `DISABLED` |

Do not invent additional values in code; record and document the business transition first.

## Events and acronyms

- Audit `event_type` uses past-tense `snake_case`: `verification_approved`, `appointment_cancelled`.
- `target_type` uses singular `snake_case`: `enrollment_verification`.
- Keep established acronyms uppercase in prose/types (`CORFile`, `SOSCase`, `APIError`) and lowercase inside compound `snake_case` (`cor_file`, `sos_case`).
- DFD labels such as `P1`, `P21`, and `D7` are diagram references only, never production identifiers.
