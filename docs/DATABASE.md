# CounselConnect — Database Contract

**Engine/tooling:** MySQL 8.4 LTS; SQLAlchemy 2.0; PyMySQL; Alembic. Store timestamps in UTC and display `Asia/Manila`. Naming is governed by `.ai/NAMING_CONVENTIONS.md`.

## V1 tables

| Group | Tables |
|---|---|
| Identity/academics | `users`, `student_profiles`, `campuses`, `departments`, `programs` |
| Sessions | `user_sessions` |
| Enrollment | `enrollment_verifications`, `enrollment_verification_files` |
| Appointments | `availability_slots`, `appointments` |
| Messaging | `conversations`, `messages` |
| SOS | `sos_cases`, `sos_responses` |
| Resources | `resource_sources`, `wellness_resources`, `resource_files`, `resource_categories`, `wellness_resource_categories` |
| Content/operations | `content_items`, `emergency_contacts`, `audit_events` |

`enrollment_verification_files` stores temporary metadata references only, never COR bytes. `resource_files` refers only to controlled durable internal resource attachments.

## Appointment and conversation fields

- `campuses.guidance_office_location`: Counselor-managed campus-level onsite location; may be null until configured.
- `availability_slots.delivery_mode`: `ONLINE`, `FACE_TO_FACE`, or `BOTH`.
- `appointments.appointment_mode`: Student-selected `ONLINE` or `FACE_TO_FACE` compatible with the slot.
- `appointments.meeting_location`: required booking-time campus-location snapshot for face-to-face appointments; null for online appointments.
- `appointments.conversation_id`: nullable unique FK to the dedicated scheduled online conversation.
- `conversations.conversation_type`: `GENERAL`, `APPOINTMENT`, or `SOS`.

Application services must enforce cross-table rules that a row-local SQL `CHECK` cannot:

- A selected appointment mode must be supported by the slot's `delivery_mode`.
- `FACE_TO_FACE` or `BOTH` availability requires a configured Guidance Office location for the slot's campus.
- A face-to-face request copies that campus value into `meeting_location` within the booking transaction.
- A linked appointment conversation requires a confirmed online appointment at the scheduled start.
- The appointment and conversation Student/Counselor pairs must match.
- Face-to-face appointments cannot link conversations.
- One conversation cannot be linked to both an appointment and SOS case.

## Integrity/lifecycle

- Foreign keys and unique constraints enforce identity, ownership, canonical URLs, student numbers, program codes, category slugs, message idempotency, and appointment-conversation uniqueness where defined by the ERD.
- Use transactions for atomic record changes; external file deletion remains separately detectable/retryable.
- Booking locks and revalidates the slot, mode compatibility, and location requirements before reserving the slot and inserting the appointment.
- Index actual query paths: status/queue timestamps, `valid_until`, campus/mode/open-slot searches, Counselor/Student appointment ranges, online-session links, open conversations/SOS cases, resource status/categories/canonical URL.
- Alembic owns deployed schema changes; no ad-hoc production patches. The first Alembic revision (`8f0f8c585641`) is a no-op baseline stamped onto the approved v4.1 initialization SQL; schema changes after the baseline are Alembic migrations (the first is `297c92da239d`, adding `user_sessions`).
- Retention jobs handle seven-day COR expiry and 30-day post-closure message-body purge.
- `user_sessions` stores only SHA-256 digests (BINARY(32)) of the opaque session credential and its CSRF token — never raw credentials. `user_id` cascades on user deletion (sessions are ephemeral credentials, not history; `audit_events` remains the durable record). `last_activity_at` moves only on genuine user action and is clamped so it can never exceed `absolute_expires_at`; cleanup removes expired/revoked sessions.

## Forbidden persistence

No COR blob/base64, raw camera media, embeddings/biometric templates, observed-expression history, assistant history, recordings/transcripts/summaries, or mirrored third-party article bodies.

## Intentionally absent in V1

No role/permission join model, separate Counselor/admin profiles, profile-change requests, recurrence/history/notification tables, conversation participant/read-receipt/transcript tables, SOS question/rule tables, emotion tables, resource review-history/tag tables, assistant history, or CMS version/draft/schedule tables.
