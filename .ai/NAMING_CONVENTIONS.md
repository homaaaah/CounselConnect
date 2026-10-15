# CounselConnect — Naming Conventions

Authoritative for new APIs, schemas, database objects, events, and source files. Preserve existing diagram/ERD names unless a migration intentionally changes them.

## Canonical domain language

| Display term | Code value / identifier |
|---|---|
| Student | `STUDENT`, `student` |
| Guidance Staff | `GUIDANCE_STAFF`, `guidance_staff` |
| Guidance Counselor / Counselor | `COUNSELOR`, `counselor` |
| Certificate of Registration | `COR`, `cor` |
| COR screening | `cor_screening` |
| Guidance Office location | `guidance_office_location` |
| Availability delivery mode | `delivery_mode` |
| Appointment mode | `appointment_mode` |
| Meeting-location snapshot | `meeting_location` |
| Conversation type | `conversation_type` |
| Observed Expression Cue | `observed_expression_cue` |
| SOS | `SOS`, `sos` |

Never introduce `ADMIN`, `administrator`, `student_id` evidence, `emotional_baseline` persistence, or identity/face-recognition terms. The narrow `SUPERADMIN` recovery role (ADR-030) is the only staff-elevation exception. “Observed Expression Cue” is session context, not a stored student trait.

## Case by layer

| Layer | Convention | Example |
|---|---|---|
| Python files/functions/variables | `snake_case` | `cor_screening.py`, `confirm_screening` |
| Python/JavaScript classes, React components | `PascalCase` | `CorScreeningResponse`, `SOSCaseCard` |
| React hooks | `useCamelCase` | `useAppointmentSlots` |
| TS/JS variables/functions/props | `camelCase` | `verificationStatus` |
| Constants/enum values/error codes | `SCREAMING_SNAKE_CASE` | `NEEDS_RESUBMISSION`, `SLOT_UNAVAILABLE` |
| Database/API JSON/query fields | `snake_case` | `student_user_id`, `valid_until` |
| Database tables | plural `snake_case` | `cor_screenings` |
| URL resource segments | plural `kebab-case` | `/cor-screenings` |
| Environment variables | `COUNSELCONNECT_` + uppercase | `COUNSELCONNECT_DATABASE_URL` |
| Tests | mirror target + `_test`/`.test` | `test_appointments.py`, `AppointmentCard.test.jsx` |

Keep API DTO fields exactly `snake_case` in frontend API types; use `camelCase` only inside UI logic. Do not add silent global case conversion.

## Database

- Table: plural noun; PK: singular entity + `_id` (`users.user_id`, `appointments.appointment_id`).
- FK: referenced role/entity + `_id` (`student_user_id`, `reviewed_by_user_id`). Add role qualifiers when one table references `users` more than once.
- Boolean: `is_`, `has_`, or `can_`; timestamp: `_at`; calendar date: established domain name such as `valid_until`.
- Use created/updated timestamps only when needed. Store timestamps in UTC.
- Junction table combines plural entities; composite FKs form the PK (`wellness_resource_categories`).
- Status columns are `status`; specialized outputs use explicit names (`urgency_result_code`, `cleanup_state`).
- Use `delivery_mode` for a slot's supported delivery capability and `appointment_mode` for the Student's selected mode.
- Use `guidance_office_location` for the Counselor-managed campus value and `meeting_location` for the immutable face-to-face appointment snapshot.
- Use `conversation_type` to distinguish `GENERAL`, `APPOINTMENT`, and `SOS`; do not overload conversation `status` for purpose.
- JSON columns end `_json`; byte counts end `_bytes`; ordered UI fields use `display_order`.
- Credential/token digests end `_hash` and store a SHA-256 `BINARY(32)`; an issuance time is `_issued_at` (e.g. `verification_token_hash`, `verification_token_issued_at`). Never store a raw token or a boolean "used" flag when clearing the digest signals invalidation.
- Do not prefix every column with its table name. Do not store COR blobs, expression cues, raw facial media, or assistant history.

The v1 table names in `docs/DATABASE.md` are canonical.

## HTTP API

- Base path: `/api/v1`.
- Use plural noun resources and standard verbs: `GET` read, `POST` create/transition, `PATCH` partial update, `DELETE` removal.
- Use `{entity_id}` path variables: `/appointments/{appointment_id}`.
- Nest only for ownership/context: `/conversations/{conversation_id}/messages`.
- Query parameters are `snake_case`: `?status=PENDING&page=1&page_size=20`.
- State transitions may use explicit action endpoints when a plain CRUD update would hide business rules:
  - `POST /cor-screenings/confirm`
  - `POST /cor-screenings/reject`
  - `POST /appointments/{appointment_id}/confirm`
  - `POST /sos-cases/{sos_case_id}/close`
  - `POST /wellness-resources/{resource_id}/publish`
- Auth action exceptions use `/auth/login`, `/auth/refresh`, `/auth/logout`.
- The one-time COR verification credential travels in the `X-COR-Token` request header (never a cookie, URL, or query); its failure code is `INVALID_VERIFICATION_TOKEN`. Session CSRF stays in `X-CSRF-Token`.
- Student profile-edit requests use `POST /cor-screenings/request-edit`; review uses the `/profile-change-requests` resource (`approve`/`reject`) (ADR-032).
- Registration/self-service codes include `SCREENING_FAILED` (technical screening failure created no account) and `ACCOUNT_NOT_REJECTABLE` (self-cancellation of an active account) (ADR-033).
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
| Role | `STUDENT`, `GUIDANCE_STAFF`, `COUNSELOR`, `SUPERADMIN` |
| Verification (legacy `enrollment_verifications`) | `PENDING`, `APPROVED`, `NEEDS_RESUBMISSION`, `REJECTED`, `EXPIRED` |
| COR screening | `PROCESSING`, `AWAITING_CONFIRMATION`, `PASSED`, `NEEDS_RESUBMISSION`, `FAILED` |
| Profile change request | `PENDING`, `APPROVED`, `REJECTED` |
| COR barcode | `NOT_PROCESSED`, `NOT_FOUND`, `UNREADABLE`, `INVALID_FORMAT`, `DECODED`, `MISMATCH` |
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

- Audit `event_type` uses past-tense `snake_case`: `cor_screening_submitted`, `account_activated`, `account_rejected`, `appointment_cancelled`, `profile_change_approved`.
- `target_type` uses singular `snake_case`: `cor_screening`, `profile_change_request`, `user`.
- Keep established acronyms uppercase in prose/types (`CORFile`, `SOSCase`, `APIError`) and lowercase inside compound `snake_case` (`cor_file`, `sos_case`).
- DFD labels such as `P1`, `P21`, and `D7` are diagram references only, never production identifiers.
