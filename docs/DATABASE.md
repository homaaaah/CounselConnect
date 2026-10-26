# CounselConnect — Database Contract

**Engine/tooling:** MySQL 8.4 LTS; SQLAlchemy 2.0; PyMySQL; Alembic. Store timestamps in UTC and display `Asia/Manila`. Naming is governed by `.ai/NAMING_CONVENTIONS.md`.

## Correction schema increment and remaining target

Task 3.1 adds migration `20261025_correction_context` after `20261024_weekly_sched_softdel` and matching ORM fields on `profile_change_requests`: nullable submission version, previous/root request IDs, `extracted_values_json`, `registered_values_json`, baseline `registered_cor_screening_id`, and evidence file ID/SHA-256/upload/expiry metadata. Existing requested fields/decisions are preserved; historical context stays SQL NULL. Self-references and baseline-screening FKs restrict deletion; evidence file ID deliberately has no FK to disposable file metadata. Unique predecessor/root-version constraints prevent branching/duplicate version numbers. First rows use their own ID as logical root with null root pointer. The schema permits `RETURNED` alongside historical `REJECTED`; existing endpoints still use legacy statuses. Upgrade retries tolerate interrupted additive DDL; downgrade refuses populated new context or `RETURNED` decisions instead of discarding them.

Task 3.2 adds migration `20261025_account_screening_scope` after the context migration. `users.is_deactivated` is non-null with false as both database/ORM default and a 0/1 check; it is separate from `account_status`. `cor_screenings.purpose` is non-null with default `REGISTRATION` and a `REGISTRATION`/`CORRECTION` check. Existing records retain their account/screening statuses, fields, and timestamps. Downgrade refuses any deactivated account or non-registration screening before dropping either field. Upgrades tolerate partially committed additive DDL; stop application writers before migration/rollback.

[REGISTRATION_CORRECTIONS.md](REGISTRATION_CORRECTIONS.md) owns the full target. These schema increments do not implement deactivation enforcement or correction-only screening creation/isolation. Task 4.3 implements bounded pending-correction retention through existing file/request/audit tables; no new migration is needed. No endpoint writes the new non-default states yet. Task 4.2 now populates version-1 metadata, original structured extraction, the confirmation-established registered baseline, baseline screening ID, and original evidence ID/digest/upload/expiry for new changed submissions. Snapshot recording never extends the original deadline; Task 4.3 retains exact pending evidence only until that deadline, a decision or replacement. Historical context remains null. Task 4.4 adds `20261025_pending_correction`: virtual `pending_student_user_id` equals the stable owner only for PENDING rows, otherwise null; `uq_profile_change_requests_pending_student` enforces uniqueness across all contexts and legacy versions. Terminal rows release the slot automatically. Existing FK actions, snapshots, statuses, timestamps and decisions are unchanged. The derived field is internal and excluded from DTOs. Duplicate pending owners cause preflight refusal before DDL, with no automatic record decisions. Retry after partial addition is supported; downgrade removes only the key/derived column. Stop writers before migration/rollback. Application database migration remains an explicit deployment operation. No new historical correction context is inferred. Do not apply initialization SQL to existing databases.

## V1 tables

| Group | Tables |
|---|---|
| Identity/academics | `users`, `student_profiles`, `campuses`, `departments`, `programs` |
| Sessions | `user_sessions` |
| Enrollment | `cor_screenings`, `cor_screening_files` (ADR-029), `profile_change_requests` (ADR-032). Legacy `enrollment_verifications`, `enrollment_verification_files` are retained for history. |
| Appointments | `counselor_weekly_schedules`, `counselor_availability_blocks`, `counselor_blocked_dates`, `availability_slots`, `appointments`, `session_records`, `session_documents` |
| Messaging | `conversations`, `messages` |
| SOS | `sos_cases`, `sos_responses` |
| Resources | `resource_sources`, `wellness_resources`, `resource_files`, `resource_categories`, `wellness_resource_categories` |
| Content/operations | `content_items`, `emergency_contacts`, `audit_events` |

`cor_screening_files` stores temporary metadata references only, never COR bytes. `resource_files` refers only to controlled durable internal resource attachments. `cor_screenings` also stores the one-time `verification_token_hash` (SHA-256 digest) and `verification_token_issued_at` used for in-modal confirmation (ADR-031); the raw token is never stored. `profile_change_requests` stores a Student's requested names/year_level/section with a `PENDING`/`APPROVED`/`REJECTED` status for Superadmin review (ADR-032).

## Appointment and conversation fields

- `campuses.guidance_office_location`: Counselor-managed campus-level onsite location; may be null until configured.
- `availability_slots.delivery_mode`: `ONLINE`, `FACE_TO_FACE`, or `BOTH`.
- `counselor_weekly_schedules`: active, university-local recurring schedule definitions. `day_of_week` uses ISO values 1 (Monday) through 7 (Sunday); `start_time` and `end_time` are local schedule times, while generated slot timestamps remain UTC.
- `counselor_weekly_schedules.is_deleted`: soft-delete marker (default `FALSE`, migration `20261024_weekly_sched_softdel`). Deleting a schedule hides it from schedule lists and future slot generation while preserving the row and existing slot/appointment references; recreating the same definition restores the row.
- `counselor_availability_blocks`: temporary UTC intervals during which the Counselor is unavailable. They retain no appointment changes and may not overlap an active appointment when created through the service layer.
- `counselor_blocked_dates`: Counselor-owned whole-day calendar overrides; these dates are excluded from the Counselor's bookable calendar.
- `availability_slots.weekly_schedule_id`: nullable provenance link for slots generated from a weekly schedule. Legacy and concrete one-off slots remain valid with `NULL`.
- `appointments.appointment_mode`: Student-selected `ONLINE` or `FACE_TO_FACE` compatible with the slot.
- `appointments.meeting_location`: required booking-time campus-location snapshot for face-to-face appointments; null for online appointments.
- `appointments.concern_categories` / `concern_details` (migration `20261026_appointment_concerns`): nullable ordered JSON category values and up to 500 characters of Student-provided context. Null remains valid for historical appointments; new bookings require at least one supported category. The first array entry is the priority. The API returns these only to the Student and assigned Counselor; they remain separate from `session_records.presenting_concern` and are not copied into notifications, audit content, or routine logs.
- `appointments.conversation_id`: nullable unique FK to the dedicated scheduled online conversation.
- `appointments.student_reminder_dispatched_at` / `counselor_reminder_dispatched_at`: nullable markers for successfully queued appointment reminders.
- `session_records`: one row per appointment (`appointment_id` unique) holding the Counselor's private `notepad` and the assessment fields; `status` is `DRAFT` or `FINAL` (`chk_session_records_status`). The notepad is never returned to a Student; only a finalized assessment is.
- `session_documents`: appointment-scoped file metadata (uploader, filename, MIME type, size, SHA-256, opaque `storage_key`, soft-delete actor/time). Bytes live outside MySQL under the private session-document store; they are never served from a static path.
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
- Session records are writable only while the appointment is `CONFIRMED` or `COMPLETED`; a finalized record is immutable except for a Counselor reopen on a still-`CONFIRMED` appointment. Session files may be uploaded only in those two statuses and are soft-deleted, keeping metadata while bytes are removed. V1 has no automatic retention purge (ADR-P12 pending).
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

No role/permission join model, separate Counselor/admin profiles, recurrence-history or notification tables, conversation participant/read-receipt/transcript or conversation-attachment tables (session files are appointment-scoped), SOS question/rule tables, emotion tables, resource review-history/tag tables, assistant history, or CMS version/draft/schedule tables. Recurring availability definitions are stored in `counselor_weekly_schedules`; Student profile edits are stored in `profile_change_requests`.
