# CounselConnect — Database Contract

**Engine/tooling:** MySQL 8.4 LTS; SQLAlchemy 2.0; PyMySQL; Alembic. Store timestamps in UTC and display `Asia/Manila`. Naming is governed by `.ai/NAMING_CONVENTIONS.md`.

## V1 tables

| Group | Tables |
|---|---|
| Identity/academics | `users`, `student_profiles`, `campuses`, `departments`, `programs` |
| Sessions | `user_sessions` |
| Enrollment | `enrollment_verifications`, `enrollment_verification_files` |
| Appointments | `counselor_weekly_schedules`, `counselor_availability_blocks`, `availability_slots`, `appointments` |
| Messaging | `conversations`, `messages` |
| SOS | `sos_cases`, `sos_responses` |
| Resources | `resource_sources`, `wellness_resources`, `resource_files`, `resource_categories`, `wellness_resource_categories` |
| Content/operations | `content_items`, `emergency_contacts`, `audit_events` |

`enrollment_verification_files` stores temporary metadata references only, never COR bytes. `resource_files` refers only to controlled durable internal resource attachments.

## Appointment and conversation fields

- `campuses.guidance_office_location`: Counselor-managed campus-level onsite location; may be null until configured.
- `availability_slots.delivery_mode`: `ONLINE`, `FACE_TO_FACE`, or `BOTH`.
- `counselor_weekly_schedules`: active, university-local recurring schedule definitions. `day_of_week` uses ISO values 1 (Monday) through 7 (Sunday); `start_time` and `end_time` are local schedule times, while generated slot timestamps remain UTC.
- `counselor_availability_blocks`: temporary UTC intervals during which the Counselor is unavailable. They retain no appointment changes and may not overlap an active appointment when created through the service layer.
- `availability_slots.weekly_schedule_id`: nullable provenance link for slots generated from a weekly schedule. Legacy and concrete one-off slots remain valid with `NULL`.
- `appointments.appointment_mode`: Student-selected `ONLINE` or `FACE_TO_FACE` compatible with the slot.
- `appointments.meeting_location`: required booking-time campus-location snapshot for face-to-face appointments; null for online appointments.
- `appointments.conversation_id`: nullable unique FK to the dedicated scheduled online conversation.
- `appointments.student_reminder_dispatched_at` / `counselor_reminder_dispatched_at`: nullable markers for successfully queued appointment reminders.
- `conversations.conversation_type`: `GENERAL`, `APPOINTMENT`, or `SOS`.
- `conversations.appointment_id`: nullable unique reverse link used to enforce one conversation per scheduled appointment; join timestamps, closure reason, and the last sequence number record the chat lifecycle.
- `messages.sequence_number`: required conversation-local durable order, unique with `conversation_id`; `client_message_id` remains the retry/idempotency key.

Application services must enforce cross-table rules that a row-local SQL `CHECK` cannot:

- A selected appointment mode must be supported by the slot's `delivery_mode`.
- `FACE_TO_FACE` or `BOTH` availability requires a configured Guidance Office location for the slot's campus.
- A face-to-face request copies that campus value into `meeting_location` within the booking transaction.
- A linked appointment conversation requires a confirmed online appointment at the scheduled start.
- The appointment and conversation Student/Counselor pairs must match.
- Face-to-face appointments cannot link conversations.
- One conversation cannot be linked to both an appointment and SOS case.
- A Counselor's active weekly periods must not overlap. MySQL checks cannot compare other rows, so overlap detection is a locked service/repository operation.
- A schedule duration must divide its configured time range without a partial final slot. `FACE_TO_FACE` and `BOTH` schedules require a configured campus Guidance Office location.
- Bookable slots exclude inactive schedules, temporary blocks, active appointments, and past times. A block cannot be saved if it overlaps a `PENDING` or `CONFIRMED` appointment; it never cancels, rejects, reschedules, or moves an appointment.
- Changing recurring availability deactivates the old schedule and inserts a replacement. On materialization, matching future `AVAILABLE` slots adopt the active definition's delivery mode and schedule link; leftover available slots linked to an inactive definition are excluded from calendars and booking. `RESERVED` slots and existing appointments remain unchanged.
- Only the assigned Counselor may record `COMPLETED` or `NO_SHOW` for a confirmed face-to-face appointment, and that transition must create an `audit_events` entry. The status endpoint is not part of the persistence migration.

## Integrity/lifecycle

- Foreign keys and unique constraints enforce identity, ownership, canonical URLs, student numbers, program codes, category slugs, message idempotency, and appointment-conversation uniqueness where defined by the ERD.
- Use transactions for atomic record changes; external file deletion remains separately detectable/retryable.
- Booking locks and revalidates the slot, mode compatibility, and location requirements before reserving the slot and inserting the appointment.
- Index actual query paths: status/queue timestamps, `valid_until`, campus/mode/open-slot searches, Counselor/Student appointment ranges, online-session links, open conversations/SOS cases, resource status/categories/canonical URL.
- Alembic owns deployed schema changes; no ad-hoc production patches. The first Alembic revision (`8f0f8c585641`) is a no-op baseline stamped onto the approved v4.1 initialization SQL; schema changes after the baseline are Alembic migrations (the first is `297c92da239d`, adding `user_sessions`).
- Implemented migration `20260910_recurring_schedules` adds weekly schedules, temporary blocks, and the optional slot provenance FK. It preserves existing appointment and slot rows. Booking-horizon policy and automatic slot-generation jobs remain pending.
- Implemented migration `20260916_scheduled_chat` validates/backfills legacy appointment links and message sequence numbers, then adds scheduled-chat lifecycle columns and integrity constraints.
- Retention jobs handle seven-day COR expiry and 30-day post-closure message-body purge.
- The implemented COR worker runs in the FastAPI lifespan and retains failed file deletions as `cleanup_state=FAILED`; no schema migration is required. UUID markers in private temporary storage cover interrupted writes before a DB commit. Operational details are in `REGISTRATION_VERIFICATION.md`.
- `user_sessions` stores only SHA-256 digests (BINARY(32)) of the opaque session credential and its CSRF token — never raw credentials. `user_id` cascades on user deletion (sessions are ephemeral credentials, not history; `audit_events` remains the durable record). `last_activity_at` moves only on genuine user action and is clamped so it can never exceed `absolute_expires_at`; cleanup removes expired/revoked sessions.

## Forbidden persistence

No COR blob/base64, raw camera media, embeddings/biometric templates, observed-expression history, assistant history, recordings/transcripts/summaries, or mirrored third-party article bodies.

## Intentionally absent in V1

No role/permission join model, separate Counselor/admin profiles, profile-change requests, recurrence/history/notification tables, conversation participant/read-receipt/transcript tables, SOS question/rule tables, emotion tables, resource review-history/tag tables, assistant history, or CMS version/draft/schedule tables.
