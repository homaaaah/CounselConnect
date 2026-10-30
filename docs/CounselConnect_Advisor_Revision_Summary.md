CounselConnect Advisor Revision Summary and Implementation Start Plan

# Purpose

This document consolidates the approved CounselConnect scope revision, its system-design consequences, the remaining decisions, and the recommended order for beginning implementation. It is a working guide for the development team and does not convert pending items into approved policy.

# 1. Revision Overview

The revision changes CounselConnect from a system centered on manual COR review and wellness-resource discovery into a counseling platform centered on automated Student registration, multi-Counselor operations, scheduled online sessions, durable counseling records, private clinical-document handling, and optional AI-assisted session observation.

- Manual Guidance Staff COR verification is replaced by automated COR format screening, OCR-based data extraction, and embedded-barcode screening.
- The system must support multiple Counselor accounts and adds a separate Superadmin role.
- Appointments gain required concern information.
- Scheduled online counseling retains text chat and adds planned one-to-one audio/video calls.
- Counseling sessions gain statuses, private Counselor notes, finalized assessments, Student-visible history, correction requests, and amendments.
- Students and assigned Counselors may upload private referral, diagnosis, and prescription documents.
- AI assistance becomes an optional, consent-based, non-diagnostic observation tool during online sessions.
- The Wellness Resource Library and automated resource-discovery feature are removed completely.

# 2. Approved Product and Technical Decisions

## 2.1 Registration and Automated COR Screening

- The Student provides an email address, password, and a readable COR image or PDF.
- The password is hashed using Argon2id; the raw password is never stored.
- The uploaded COR is kept temporarily in private storage rather than a public or static folder.
- The system validates file type, file size, readability, expected layout, required fields, internal consistency, and the barcode requirements defined by the approved COR template version.
- OCR extracts the Student Number, name, course or program, year level, section, campus, academic period, and other approved fields. The barcode reader validates expected presence, readability, allowed symbology and payload structure, and consistency with OCR-extracted identifiers when encoded.
- The Student reviews and confirms the extracted information before the account becomes active.
- Uncertain, incomplete, low-confidence, unreadable, barcode-missing, barcode-invalid, or barcode-mismatched submissions request resubmission instead of silently approving the account.
- Duplicate email and Student Number checks prevent a second account from being activated for the same Student.
- After activation, a Student may sign in using either the registered email address or Student Number.
- Format, OCR, and barcode screening do not prove that UCC issued the COR. Verification of decoded barcode data against a University-controlled registrar database, signed payload, or equivalent source remains pending.

## 2.2 User Roles and Authority

- Target roles are STUDENT, COUNSELOR, and SUPERADMIN.
- Guidance Staff is removed only after the automated registration replacement and data migration are working.
- The architecture must support multiple Counselor users, each with separate schedules, appointments, assigned Students, conversations, counseling records, and access checks.
- Superadmin manages accounts, system configuration, operational auditing, correction-request routing, and system oversight.
- Superadmin has no default access to private counseling notes, message bodies, assessments, uploaded clinical documents, or call content.
- The assigned Counselor remains responsible for counseling content and final assessments.

## 2.3 Appointment Scheduling

- Appointment requests require a concern_category and may include optional concern_details.
- Concern information is sensitive and is visible only to the Student and assigned Counselor.
- Concern text must not appear in generic reminders, notification previews, or ordinary application logs.
- Existing weekly Counselor schedules, blocked times, materialized availability slots, booking limits, cancellation rules, and multiple-Counselor behavior remain in effect.

## 2.4 Scheduled Text Chat and Audio/Video Calls

- Scheduled text chat remains linked to a confirmed online appointment.
- The launcher becomes available 30 minutes before the appointment, and the approved safety deadline remains the scheduled end plus 15 minutes.
- General or out-of-session chat is not part of this revision because its workflow is not finalized.
- One-to-one audio/video calling will use WebRTC with authenticated FastAPI signaling.
- Only the Student and assigned Counselor for the appointment may join during the allowed session window.
- Version 1 will not record calls or persist audio, video, SDP, ICE credentials, transcripts, screenshots, automatic summaries, or derived call artifacts.
- Text chat remains available during the online session even when audio/video calling is used.

## 2.5 Counseling Session Records

- Each appointment has a trackable counseling-session record with states such as SCHEDULED, IN_PROGRESS, ENDED, DOCUMENTATION_PENDING, and FINALIZED.
- The assigned Counselor may write private draft notes during or after the session.
- Private draft notes are not visible to Students or Superadmin.
- The Counselor creates and finalizes a structured assessment. The durable assessment is authored by the Counselor, not automatically generated by AI.
- Students have read-only access to their own finalized assessments and later amendments.
- During a later assigned session, the Counselor may view the Student's relevant prior finalized session history.
- A finalized assessment is immutable. Corrections use a Student-visible correction request and an append-only amendment by the assigned Counselor.
- Superadmin may route and monitor correction requests but cannot author, replace, or silently edit clinical content.

## 2.6 Referral, Diagnosis, and Prescription Files

- Students and assigned Counselors may upload approved image or PDF files for external referrals, diagnosis papers, and prescriptions.
- MySQL stores metadata, ownership, storage key, type, size, hash, and lifecycle state; it does not store the file bytes.
- Development uses a private local directory configured through environment settings.
- Every download requires authentication and authorization based on the Student, uploader, assigned Counselor, and related session.
- The production storage provider, encryption and backup operations, deletion procedure, and final retention period remain pending.

## 2.7 AI-Assisted Multimodal Session Observation

- The feature is optional and may be enabled by the Counselor only with informed Student consent during an online call.
- The initial design combines local facial-observation cues, Student self-report, and non-clinical trend or context summaries.
- Voice or prosody analysis is deferred and must not be added without a separate privacy review and decision.
- Outputs use observable, non-diagnostic wording and include confidence or uncertainty. Examples are reduced facial expressiveness, repeated gaze aversion, or self-reported low mood.
- The AI must not output diagnoses or condition labels such as depressed, depression, anxiety disorder, or similar clinical conclusions.
- AI observations are optional secondary context only. They never replace the Counselor's professional judgment and never affect SOS triage.
- Raw audio, raw video, facial embeddings, transcripts, observation history, and AI-generated clinical conclusions are not persisted.
- Only the Counselor's independently written finalized assessment becomes a durable counseling record.

## 2.8 Wellness Resource Feature Removal

- Remove the Wellness Resource Library, automated web discovery, manual resource publication, source and category management, background discovery jobs, and resource-review queues.
- Remove related pages, API routes, database tables, tests, fixtures, seeds, scheduled jobs, and documentation.
- Remove the resource-backed assistant with the library.
- A small navigation or FAQ-only assistant remains a pending decision and must not provide counseling or diagnostic advice.
- The research title and written scope must be revised because they must no longer claim automated wellness-resource discovery.

# 3. Database and Data-Migration Impact

CounselConnect_Target_Database_v5.sql is the approved clean-install target snapshot. It contains 27 tables and folds the current session, recurring-schedule, availability-block, and scheduled-chat migrations into the revised design.

- New or revised areas include users and roles, user sessions, automated COR screenings with safe barcode metadata, temporary COR file metadata, appointments with concern fields, counseling sessions, private notes, finalized assessments, correction requests, amendments, call-session metadata, and clinical-document metadata.
- Wellness-resource and manual enrollment-verification tables are absent from the target schema.
- AI observation has no persistence table because the approved design is session-only.
- The v5 SQL is for a new empty database. It must not be executed over the current development database.
- Existing databases must be upgraded through reviewed Alembic revisions from the current migration head.
- The v4.1 SQL remains the historical baseline and must not be overwritten.
- A clean MySQL 8.4 import and a complete migration rehearsal are still required before the schema is considered executable-final.

# 4. Pending Decisions

- Exact SOS questions, thresholds, availability fallback, and privacy notice require Guidance Office approval.
- Capacitor session transport, production password-reset email delivery, and Counselor-assisted recovery remain pending.
- Authoritative verification of decoded barcode data against a University-controlled registrar source, signed payload, or equivalent method remains pending. Version 1 performs barcode decoding and internal consistency checks only.
- The production private-file storage provider, encryption/key handling, backup method, and deletion process remain pending.
- Retention periods for finalized assessments, amendments, clinical documents, and related audit metadata remain pending.
- Whether a navigation or FAQ-only assistant remains is pending.
- Voice or prosody observation is excluded until separately approved.
- Email ownership verification is not yet represented in the v5 target database and must be decided before production.
- Approved COR templates, confidence thresholds, upload limits, retry limits, and temporary-file cleanup period require testing with representative COR samples.
- A revised research title must be approved because the previous title refers to the removed wellness-resource feature.

# 5. Recommended Steps to Start the Revision

## Step 1 — Freeze and Communicate the New Scope

1. Hold a short team review of ADR-029 through ADR-037 and the pending decisions.
2. Mark the old Guidance Staff, manual COR review, Wellness Resource Library, resource discovery, and resource-backed assistant as superseded scope.
3. Do not start unrelated feature work until every developer understands the new roles, privacy boundaries, and removed features.
4. Create small acceptance criteria for each revised feature and identify the responsible backend, frontend, database, testing, and documentation owner.

## Step 2 — Protect the Current Working Version

1. Merge or close current pull requests deliberately and ensure the existing main branch is stable.
2. Create a recoverable tag or release snapshot of the current pre-revision version.
3. Back up the current development database before testing any migration.
4. Create a revision branch, such as revision/advisor-scope-update, and continue using feature branches and pull requests rather than committing directly to main.

## Step 3 — Convert the Target Schema into Alembic Revisions

1. Do not run the clean-install v5 SQL against the current database.
2. Create an ordered migration plan: target roles and Superadmin; automated COR screening; appointment concern fields; counseling records; clinical documents; call metadata; then removed resource tables.
3. Define how existing users and foreign keys will be mapped before removing Guidance Staff.
4. Seed the first Superadmin through controlled environment configuration or a one-time administrative command; never hard-code a production password.
5. Test upgrade and downgrade behavior on a disposable copy of the development database.
6. Generate a fresh database from the full Alembic chain and compare it with the v5 target snapshot.

## Step 4 — Build the Registration Vertical Slice First

1. Implement private COR upload, safe file metadata, and cleanup behavior.
2. Implement OCR extraction, COR template matching, and barcode decoding behind service interfaces so individual components can be replaced without rewriting registration.
3. Implement screening states, confidence handling, duplicate checks, Student confirmation, resubmission, and atomic account activation.
4. Add Student login resolution for either email or Student Number.
5. Build the frontend states for upload, processing, confirmation, resubmission, failure, and success.
6. Test valid, unreadable, wrong-format, low-confidence, missing-barcode, unreadable-barcode, invalid-payload, barcode-mismatch, duplicated, concurrent, oversized, and unsupported-file scenarios.

## Step 5 — Complete Role and Authorization Migration

1. Replace Guidance Staff routes, menus, permissions, tests, and seeds with the approved Counselor and Superadmin boundaries.
2. Verify every Counselor query is scoped by the assigned counselor_user_id rather than assuming one Counselor exists.
3. Verify Superadmin operational pages do not expose counseling notes, messages, assessments, clinical documents, or call data by default.

## Step 6 — Add Appointment Concern Fields

1. Add concern_category and optional concern_details through Alembic, SQLAlchemy, API schemas, validation, and frontend forms.
2. Restrict visibility to the Student and assigned Counselor.
3. Add tests proving concern content does not enter reminders, notification previews, audit details, or ordinary logs.

## Step 7 — Implement Counseling Session Records

1. Create the session lifecycle and status transitions linked one-to-one with an appointment.
2. Add private Counselor draft notes and enforce their visibility boundary.
3. Add Counselor-authored draft and finalized assessments, Student read-only access, and prior finalized history for the assigned Counselor.
4. Add correction requests and append-only amendments; prevent updates to finalized assessment content.
5. Test cross-Student, cross-Counselor, and Superadmin access denial.

## Step 8 — Implement Private Clinical-Document Handling

1. Create the private development storage adapter and metadata repository.
2. Validate MIME type, extension, file signature, size, ownership, and related Student or session.
3. Serve downloads through an authenticated endpoint rather than a public URL.
4. Add safe deletion and orphan-cleanup tests without logging document contents.

## Step 9 — Prototype Audio/Video Calling

1. Build a minimal two-user WebRTC prototype using authenticated FastAPI signaling.
2. Enforce appointment participant identity and allowed session time before issuing signaling access.
3. Test reconnect, permission denial, device absence, network interruption, Counselor-ended sessions, and text-chat continuity.
4. Do not add recording, transcription, or automatic summarization to the prototype.

## Step 10 — Prototype AI Observation Only After Calls Are Stable

1. Define the exact observable output labels, consent text, confidence presentation, and disable controls with Counselor and privacy review.
2. Select representative evaluation data and document model limitations, subgroup performance, false positives, and false negatives.
3. Keep inference local or otherwise privacy-contained and session-only.
4. Prove that disabling the feature does not affect the call, text chat, appointment outcome, session record, or SOS flow.
5. Do not market or label the output as diagnosis, depression detection, or mental-health condition detection.

## Step 11 — Remove the Wellness Resource Scope

1. Remove resource UI, APIs, services, jobs, database models, fixtures, tests, seeds, and documentation in a dedicated pull request.
2. Search the repository for stale resource terminology and old role names.
3. Update navigation, dashboards, diagrams, research scope, presentation materials, and the project title once the new title is approved.

## Step 12 — Run Integration, Security, and Migration Verification

1. Run unit, integration, authorization, migration, file-upload, WebSocket, and browser-flow tests.
2. Import the clean v5 SQL into an empty MySQL 8.4 database and confirm all 27 tables and constraints.
3. Migrate a disposable current database to the new head and verify data mappings, role removal, account access, and rollback strategy.
4. Conduct a privacy review focused on CORs, concern text, messages, notes, assessments, clinical files, call signaling, AI inference, logs, and backups.
5. Only merge the revision branch after the complete registration flow and critical authorization tests pass.

# 6. First Development Milestone

The first milestone should be a complete automated-registration vertical slice running on the new role model, not the audio/video or AI feature. It should demonstrate private COR upload, format/OCR/barcode screening, extraction, Student confirmation, account activation, dual-identifier login, one seeded Superadmin, multiple-Counselor-safe authorization foundations, Alembic migration tests, and removal of Guidance Staff dependencies from that path.

# 7. Definition of Ready

- The team has approved the ADRs and understands which decisions remain pending.
- Representative anonymized COR samples and approved template versions are available.
- Acceptance criteria and privacy rules exist for the selected implementation step.
- The current code and database have recoverable backups.
- The migration order and ownership assignments are documented.

# 8. Definition of Done for the Revision

- All role, registration, appointment, session-record, document-upload, scheduled communication, and approved AI boundaries match the ADRs.
- Wellness-resource functionality and obsolete Guidance Staff behavior are removed from code and documentation.
- Existing databases migrate successfully and fresh databases build successfully.
- Authorization tests prove that Students, Counselors, and Superadmin see only permitted data.
- Finalized assessments remain immutable and correction history is append-only.
- No private COR, raw decoded barcode payload, message, concern, note, assessment, document, call-media, or AI-observation content leaks into public storage, generic notifications, or logs.
- Pending items remain visibly pending rather than being silently implemented as policy.
- Research title, scope, diagrams, handbook, and defense materials accurately describe the revised system.