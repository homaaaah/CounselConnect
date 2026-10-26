# CounselConnect — Naming Conventions

Authoritative for new APIs, schemas, database objects, events, and source files. Preserve legacy names only until their planned migration is complete.

## Canonical domain language

| Display term | Code value / identifier |
|---|---|
| Student | `STUDENT`, `student` |
| Guidance Counselor / Counselor | `COUNSELOR`, `counselor` |
| Superadmin | `SUPERADMIN`, `superadmin` |
| Certificate of Registration | `COR`, `cor` |
| COR Screening | `cor_screening` |
| COR Barcode Screening | `barcode_status`, `barcode_symbology`, `barcode_decode_confidence`, `barcode_payload_hash` |
| Guidance Office location | `guidance_office_location` |
| Appointment Concern | `concern_category`, `concern_details` |
| Counseling Session | `counseling_session` |
| Session Assessment | `session_assessment` |
| Assessment Amendment | `assessment_amendment` |
| Clinical Document | `clinical_document` |
| AI-Assisted Session Observation | `session_observation` |
| Observed Cue | `observed_cue` |
| SOS | `SOS`, `sos` |

Do not introduce generic `ADMIN`/`administrator`; use `SUPERADMIN`. Do not use `GUIDANCE_STAFF` in new code. Do not use identity/face-recognition terminology for observation. AI outputs are observable cues, not stored Student traits or diagnoses.

## Case by layer

| Layer | Convention | Example |
|---|---|---|
| Python files/functions/variables | `snake_case` | `cor_screening.py`, `finalize_assessment` |
| Python/JavaScript classes, React components | `PascalCase` | `CounselingSessionResponse`, `ClinicalDocumentCard` |
| React hooks | `useCamelCase` | `useCounselingSession` |
| TS/JS variables/functions/props | `camelCase` | `concernCategory` |
| Constants/enum values/error codes | `SCREAMING_SNAKE_CASE` | `DOCUMENTATION_PENDING` |
| Database/API JSON/query fields | `snake_case` | `assigned_counselor_user_id` |
| Database tables | plural `snake_case` | `counseling_sessions` |
| URL resource segments | plural `kebab-case` | `/clinical-documents` |
| Environment variables | `COUNSELCONNECT_` + uppercase | `COUNSELCONNECT_PRIVATE_STORAGE_ROOT` |
| Tests | mirror target + `_test`/`.test` | `test_counseling_sessions.py` |

Keep API DTO fields `snake_case`; use `camelCase` only inside UI logic. Do not add silent global case conversion.

## Database

- Tables use plural nouns; PKs use singular entity + `_id`.
- FKs use the referenced role/entity + `_id`; qualify repeated user references such as `student_user_id`, `assigned_counselor_user_id`, and `authored_by_counselor_user_id`.
- Boolean fields start `is_`, `has_`, or `can_`; timestamps end `_at`; JSON columns end `_json`; byte counts end `_bytes`.
- Persist timestamps in UTC.
- Use `delivery_mode` for a slot's capability and `appointment_mode` for the selected appointment mode.
- Use `meeting_location` for the immutable face-to-face location snapshot.
- Use `conversation_type` for `GENERAL`, `APPOINTMENT`, or `SOS`; do not overload conversation status.
- Store file metadata and opaque `storage_key` values in MySQL, never private file content or public URLs.
- Do not store COR blobs, raw decoded barcode payloads, call media, recordings, transcripts, face embeddings, raw AI observations, or AI-generated diagnoses.
- Do not create new Wellness Resource tables; existing resource tables are scheduled for removal under ADR-036.

## HTTP API

- Base path: `/api/v1`.
- Use plural resource nouns and standard HTTP methods.
- Use `{entity_id}` path variables and `snake_case` query parameters.
- Nest only for ownership/context, such as `/counseling-sessions/{session_id}/assessment`.
- State transitions may use explicit actions when CRUD would hide a business rule:
  - `POST /cor-screenings/{screening_id}/confirm`
  - `POST /appointments/{appointment_id}/confirm`
  - `POST /counseling-sessions/{session_id}/start`
  - `POST /counseling-sessions/{session_id}/end`
  - `POST /counseling-sessions/{session_id}/assessment/finalize`
  - `POST /assessment-correction-requests/{request_id}/resolve`
  - `POST /sos-cases/{sos_case_id}/close`
- Auth actions use `/auth/login`, `/auth/logout`, and the documented password-reset endpoints. There is no JWT refresh route for opaque sessions.
- The one-time COR verification credential uses the `X-COR-Token` request header; session CSRF remains in `X-CSRF-Token`.
- Do not duplicate routes by role when authorization can govern one resource.

## Payloads and errors

- Schemas use `{Entity}CreateRequest`, `{Entity}UpdateRequest`, `{Entity}Response`, and `{Entity}ListResponse`.
- Lists use `{ "items": [], "page": 1, "page_size": 20, "total": 0 }`.
- Errors use `{ "error": { "code": "SLOT_UNAVAILABLE", "message": "...", "details": {} } }`.
- UTC timestamps use ISO 8601 with `Z`; dates use `YYYY-MM-DD`; enums use uppercase values.
- File uploads use `multipart/form-data`; metadata remains `snake_case`.

## Approved target states and values

| Domain | Values |
|---|---|
| Account | `PENDING_VERIFICATION`, `ACTIVE`, `VERIFICATION_EXPIRED`; `is_deactivated` is independent of enrollment status. |
| COR screening | `PROCESSING`, `AWAITING_CONFIRMATION`, `PASSED`, `NEEDS_RESUBMISSION`, `FAILED` |
| Profile change request | `PENDING`, `APPROVED`, `RETURNED`, `REJECTED` (historical) |
| COR screening purpose | `REGISTRATION`, `CORRECTION` |
| COR barcode | `NOT_PROCESSED`, `NOT_FOUND`, `UNREADABLE`, `INVALID_FORMAT`, `DECODED`, `MISMATCH` |
| Availability status | `AVAILABLE`, `RESERVED` |
| Availability delivery mode | `ONLINE`, `FACE_TO_FACE`, `BOTH` |
| Appointment mode | `ONLINE`, `FACE_TO_FACE` |
| Appointment | `PENDING`, `CONFIRMED`, `COMPLETED`, `CANCELLED`, `REJECTED`, `NO_SHOW` |
| Counseling session | `SCHEDULED`, `IN_PROGRESS`, `ENDED`, `DOCUMENTATION_PENDING`, `FINALIZED` |
| Session assessment | `DRAFT`, `FINALIZED` |
| Correction request | `PENDING`, `APPROVED`, `REJECTED`, `APPLIED` |
| Clinical document type | `REFERRAL`, `DIAGNOSIS`, `PRESCRIPTION`, `OTHER` |
| Conversation type | `GENERAL`, `APPOINTMENT`, `SOS` |
| Conversation status | `OPEN`, `CLOSED` |
| SOS case | `OPEN`, `RESPONDED`, `CLOSED` |

Do not invent additional states in code; record and document the transition first.

## Events and acronyms

- Audit `event_type` uses past-tense `snake_case`: `assessment_finalized`, `clinical_document_uploaded`.
- `target_type` uses singular `snake_case`: `counseling_session`.
- Keep established acronyms uppercase in prose/types (`CORFile`, `SOSCase`) and lowercase inside compound `snake_case` (`cor_file`, `sos_case`).
- DFD labels are diagram references only, never production identifiers.
