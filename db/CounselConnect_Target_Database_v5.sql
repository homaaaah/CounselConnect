-- ============================================================================
-- CounselConnect Target Database Schema v5.1
-- Target: MySQL 8.4 LTS
-- Status: APPROVED TARGET DESIGN / CLEAN INSTALL SNAPSHOT
-- Date: 2026-09-21
--
-- IMPORTANT:
-- 1. This file describes the approved post-revision target schema.
-- 2. It is for a NEW, EMPTY development database only.
-- 3. It is NOT an in-place migration from v4.1 or the current Alembic head.
-- 4. Existing databases must be upgraded through reviewed Alembic revisions.
-- 5. Preserve CounselConnect_Initial_Database_v4.1.sql as the historical
--    Alembic baseline; do not replace or edit it.
--
-- Major v5 changes:
-- - Roles become STUDENT, COUNSELOR, and SUPERADMIN.
-- - Manual Guidance Staff COR review is replaced by automated COR format
--   screening, OCR extraction, embedded-barcode checks, and Student confirmation.
-- - Students may authenticate using Student Number or registered email.
-- - Current session, recurring-schedule, availability-block, and scheduled
--   text-chat migrations are folded into this clean-install snapshot.
-- - Appointment concern fields are added.
-- - Counseling-session tracking, private Counselor notes, finalized
--   assessments, correction requests, and append-only amendments are added.
-- - Private referral/diagnosis/prescription document metadata is added.
-- - One-to-one audio/video call lifecycle metadata is added; media is not.
-- - Wellness Resource discovery/library tables are removed completely.
-- - AI-assisted observation remains session-only and has no persistence table.
--
-- Pending and deliberately excluded:
-- - Authoritative verification of decoded barcode data against a University-
--   controlled registrar source, signed payload, or equivalent service.
-- - Production private-storage provider and final retention schedules.
-- - Voice/prosody observation.
-- - Navigation/FAQ-only assistant.
-- ============================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS counselconnect_v5
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE counselconnect_v5;

-- ============================================================================
-- 1. IDENTITY AND ACADEMIC REFERENCE DATA
-- ============================================================================

CREATE TABLE campuses (
    campus_id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    campus_name                 VARCHAR(150) NOT NULL,
    guidance_office_location    VARCHAR(255) NULL,
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (campus_id),
    UNIQUE KEY uq_campuses_name (campus_name)
) ENGINE=InnoDB;

CREATE TABLE departments (
    department_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    department_name     VARCHAR(150) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (department_id),
    UNIQUE KEY uq_departments_name (department_name)
) ENGINE=InnoDB;

CREATE TABLE programs (
    program_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    department_id       BIGINT UNSIGNED NOT NULL,
    program_code        VARCHAR(50) NOT NULL,
    program_name        VARCHAR(200) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (program_id),
    UNIQUE KEY uq_programs_code (program_code),
    KEY idx_programs_department (department_id),

    CONSTRAINT fk_programs_department
        FOREIGN KEY (department_id)
        REFERENCES departments (department_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE users (
    user_id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email               VARCHAR(320) NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    role_code           VARCHAR(32) NOT NULL,
    account_status      VARCHAR(40) NOT NULL,
    -- Names may be NULL only while a Student's COR is still being screened.
    first_name          VARCHAR(100) NULL,
    middle_name         VARCHAR(100) NULL,
    last_name           VARCHAR(100) NULL,
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                   ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (user_id),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role_status (role_code, account_status),

    CONSTRAINT chk_users_role
        CHECK (role_code IN ('STUDENT', 'COUNSELOR', 'SUPERADMIN')),

    CONSTRAINT chk_users_account_status
        CHECK (
            account_status IN (
                'PENDING_VERIFICATION',
                'ACTIVE',
                'VERIFICATION_EXPIRED'
            )
        ),

    CONSTRAINT chk_users_name_readiness
        CHECK (
            account_status = 'PENDING_VERIFICATION'
            OR (first_name IS NOT NULL AND last_name IS NOT NULL)
        )
) ENGINE=InnoDB;

CREATE TABLE student_profiles (
    user_id             BIGINT UNSIGNED NOT NULL,
    student_number      VARCHAR(50) NOT NULL,
    campus_id           BIGINT UNSIGNED NOT NULL,
    program_id          BIGINT UNSIGNED NOT NULL,
    year_level          TINYINT UNSIGNED NOT NULL,
    section             VARCHAR(50) NOT NULL,

    PRIMARY KEY (user_id),
    UNIQUE KEY uq_student_profiles_number (student_number),
    KEY idx_student_profiles_campus (campus_id),
    KEY idx_student_profiles_program (program_id),

    CONSTRAINT fk_student_profiles_user
        FOREIGN KEY (user_id)
        REFERENCES users (user_id)
        ON DELETE CASCADE
        ON UPDATE RESTRICT,

    CONSTRAINT fk_student_profiles_campus
        FOREIGN KEY (campus_id)
        REFERENCES campuses (campus_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_student_profiles_program
        FOREIGN KEY (program_id)
        REFERENCES programs (program_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_student_profiles_year
        CHECK (year_level BETWEEN 1 AND 10)
) ENGINE=InnoDB;

-- ============================================================================
-- 2. AUTHENTICATION SESSIONS
-- ============================================================================

CREATE TABLE user_sessions (
    session_id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id                 BIGINT UNSIGNED NOT NULL,
    token_hash              BINARY(32) NOT NULL,
    csrf_token_hash         BINARY(32) NOT NULL,
    created_at              DATETIME(6) NOT NULL,
    last_activity_at        DATETIME(6) NOT NULL,
    absolute_expires_at     DATETIME(6) NOT NULL,
    revoked_at              DATETIME(6) NULL,
    revocation_reason       VARCHAR(50) NULL,

    PRIMARY KEY (session_id),
    UNIQUE KEY uq_user_sessions_token_hash (token_hash),
    KEY idx_user_sessions_user_active
        (user_id, revoked_at, absolute_expires_at),
    KEY idx_user_sessions_cleanup
        (absolute_expires_at, revoked_at),

    CONSTRAINT fk_user_sessions_user
        FOREIGN KEY (user_id)
        REFERENCES users (user_id)
        ON DELETE CASCADE
        ON UPDATE RESTRICT,

    CONSTRAINT chk_user_sessions_timeline
        CHECK (
            last_activity_at >= created_at
            AND absolute_expires_at >= last_activity_at
        ),

    CONSTRAINT chk_user_sessions_revocation_shape
        CHECK (
            (revoked_at IS NULL AND revocation_reason IS NULL)
            OR
            (revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)
        )
) ENGINE=InnoDB;

-- ============================================================================
-- 3. AUTOMATED COR FORMAT SCREENING
-- ============================================================================

CREATE TABLE cor_screenings (
    cor_screening_id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id                 BIGINT UNSIGNED NOT NULL,
    status                          VARCHAR(40) NOT NULL DEFAULT 'PROCESSING',
    format_template_version         VARCHAR(50) NOT NULL,
    format_match_score              DECIMAL(5,4) NULL,
    extraction_confidence           DECIMAL(5,4) NULL,
    barcode_status                  VARCHAR(32) NOT NULL DEFAULT 'NOT_PROCESSED',
    barcode_symbology               VARCHAR(32) NULL,
    barcode_decode_confidence       DECIMAL(5,4) NULL,
    barcode_payload_hash            BINARY(32) NULL
        COMMENT 'SHA-256 digest only; never persist the raw decoded payload',
    barcode_payload_format_valid    BOOLEAN NULL,
    barcode_student_number_match    BOOLEAN NULL,
    barcode_academic_period_match   BOOLEAN NULL,
    failure_reason_code             VARCHAR(100) NULL,
    validation_results_json         JSON NULL
        COMMENT 'Safe validation codes and scores only; never raw OCR text',
    extracted_student_number        VARCHAR(50) NULL,
    extracted_first_name            VARCHAR(100) NULL,
    extracted_middle_name           VARCHAR(100) NULL,
    extracted_last_name             VARCHAR(100) NULL,
    extracted_campus_id             BIGINT UNSIGNED NULL,
    extracted_program_id            BIGINT UNSIGNED NULL,
    extracted_year_level            TINYINT UNSIGNED NULL,
    extracted_section               VARCHAR(50) NULL,
    extracted_academic_period       VARCHAR(100) NULL,
    valid_until                     DATE NULL,
    submitted_at                    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    processing_started_at           DATETIME(6) NULL,
    processed_at                    DATETIME(6) NULL,
    confirmed_at                    DATETIME(6) NULL,

    PRIMARY KEY (cor_screening_id),
    KEY idx_cor_screenings_student_status
        (student_user_id, status, submitted_at),
    KEY idx_cor_screenings_status_queue
        (status, submitted_at),
    KEY idx_cor_screenings_validity
        (student_user_id, status, valid_until),
    KEY idx_cor_screenings_barcode_status
        (barcode_status, submitted_at),
    KEY idx_cor_screenings_campus (extracted_campus_id),
    KEY idx_cor_screenings_program (extracted_program_id),

    CONSTRAINT fk_cor_screenings_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_cor_screenings_campus
        FOREIGN KEY (extracted_campus_id)
        REFERENCES campuses (campus_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_cor_screenings_program
        FOREIGN KEY (extracted_program_id)
        REFERENCES programs (program_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_cor_screenings_status
        CHECK (
            status IN (
                'PROCESSING',
                'AWAITING_CONFIRMATION',
                'PASSED',
                'NEEDS_RESUBMISSION',
                'FAILED'
            )
        ),

    CONSTRAINT chk_cor_screenings_format_score
        CHECK (
            format_match_score IS NULL
            OR format_match_score BETWEEN 0.0000 AND 1.0000
        ),

    CONSTRAINT chk_cor_screenings_extraction_confidence
        CHECK (
            extraction_confidence IS NULL
            OR extraction_confidence BETWEEN 0.0000 AND 1.0000
        ),

    CONSTRAINT chk_cor_screenings_barcode_status
        CHECK (
            barcode_status IN (
                'NOT_PROCESSED',
                'NOT_FOUND',
                'UNREADABLE',
                'INVALID_FORMAT',
                'DECODED',
                'MISMATCH'
            )
        ),

    CONSTRAINT chk_cor_screenings_barcode_confidence
        CHECK (
            barcode_decode_confidence IS NULL
            OR barcode_decode_confidence BETWEEN 0.0000 AND 1.0000
        ),

    CONSTRAINT chk_cor_screenings_year
        CHECK (
            extracted_year_level IS NULL
            OR extracted_year_level BETWEEN 1 AND 10
        ),

    CONSTRAINT chk_cor_screenings_timeline
        CHECK (
            (processing_started_at IS NULL OR processing_started_at >= submitted_at)
            AND (processed_at IS NULL OR processed_at >= submitted_at)
            AND (confirmed_at IS NULL OR confirmed_at >= submitted_at)
        )
) ENGINE=InnoDB;

-- Temporary metadata only. Actual COR bytes remain in private storage.
CREATE TABLE cor_screening_files (
    cor_screening_file_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    cor_screening_id            BIGINT UNSIGNED NOT NULL,
    storage_key                 VARCHAR(512) NOT NULL,
    original_filename           VARCHAR(255) NOT NULL,
    mime_type                   VARCHAR(100) NOT NULL,
    size_bytes                  BIGINT UNSIGNED NOT NULL,
    sha256_hash                 BINARY(32) NOT NULL,
    expires_at                  DATETIME(6) NOT NULL,
    cleanup_state               VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    uploaded_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (cor_screening_file_id),
    UNIQUE KEY uq_cor_screening_files_storage_key (storage_key),
    KEY idx_cor_screening_files_screening (cor_screening_id),
    KEY idx_cor_screening_files_cleanup (cleanup_state, expires_at),

    CONSTRAINT fk_cor_screening_files_screening
        FOREIGN KEY (cor_screening_id)
        REFERENCES cor_screenings (cor_screening_id)
        ON DELETE CASCADE
        ON UPDATE RESTRICT,

    CONSTRAINT chk_cor_screening_files_size
        CHECK (size_bytes > 0),

    CONSTRAINT chk_cor_screening_files_cleanup_state
        CHECK (cleanup_state IN ('PENDING', 'FAILED'))
) ENGINE=InnoDB;

-- ============================================================================
-- 4. COUNSELOR AVAILABILITY AND APPOINTMENTS
-- ============================================================================

CREATE TABLE counselor_blocked_dates (
    blocked_date_id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counselor_user_id      BIGINT UNSIGNED NOT NULL,
    blocked_date           DATE NOT NULL,
    reason                 VARCHAR(255) NULL,
    created_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (blocked_date_id),
    UNIQUE KEY uq_counselor_blocked_date
        (counselor_user_id, blocked_date),
    KEY idx_counselor_blocked_dates_date (blocked_date),

    CONSTRAINT fk_blocked_dates_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE CASCADE
        ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE counselor_weekly_schedules (
    weekly_schedule_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counselor_user_id          BIGINT UNSIGNED NOT NULL,
    campus_id                  BIGINT UNSIGNED NOT NULL,
    day_of_week                TINYINT UNSIGNED NOT NULL,
    start_time                 TIME NOT NULL,
    end_time                   TIME NOT NULL,
    slot_duration_minutes      SMALLINT UNSIGNED NOT NULL,
    delivery_mode              VARCHAR(32) NOT NULL,
    is_active                  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (weekly_schedule_id),
    UNIQUE KEY uq_weekly_schedule_period
        (counselor_user_id, campus_id, day_of_week, start_time,
         end_time, slot_duration_minutes, delivery_mode),
    KEY idx_weekly_schedule_lookup
        (counselor_user_id, day_of_week, campus_id, is_active),

    CONSTRAINT fk_weekly_schedules_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_weekly_schedules_campus
        FOREIGN KEY (campus_id)
        REFERENCES campuses (campus_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_weekly_schedule_day
        CHECK (day_of_week BETWEEN 1 AND 7),

    CONSTRAINT chk_weekly_schedule_time
        CHECK (end_time > start_time),

    CONSTRAINT chk_weekly_schedule_duration
        CHECK (slot_duration_minutes BETWEEN 15 AND 240),

    CONSTRAINT chk_weekly_schedule_delivery_mode
        CHECK (delivery_mode IN ('ONLINE', 'FACE_TO_FACE', 'BOTH'))
) ENGINE=InnoDB;

CREATE TABLE counselor_availability_blocks (
    availability_block_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counselor_user_id          BIGINT UNSIGNED NOT NULL,
    starts_at                  DATETIME(6) NOT NULL,
    ends_at                    DATETIME(6) NOT NULL,
    is_all_day                 BOOLEAN NOT NULL DEFAULT FALSE,
    reason                     VARCHAR(255) NULL,
    created_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (availability_block_id),
    UNIQUE KEY uq_availability_block_period
        (counselor_user_id, starts_at, ends_at, is_all_day),
    KEY idx_availability_blocks_overlap
        (counselor_user_id, starts_at, ends_at),

    CONSTRAINT fk_availability_blocks_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_availability_block_time
        CHECK (ends_at > starts_at)
) ENGINE=InnoDB;

CREATE TABLE availability_slots (
    slot_id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counselor_user_id       BIGINT UNSIGNED NOT NULL,
    campus_id               BIGINT UNSIGNED NOT NULL,
    weekly_schedule_id      BIGINT UNSIGNED NULL,
    delivery_mode           VARCHAR(32) NOT NULL,
    starts_at               DATETIME(6) NOT NULL,
    ends_at                 DATETIME(6) NOT NULL,
    status                  VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
    created_at              DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (slot_id),
    UNIQUE KEY uq_availability_slot
        (counselor_user_id, campus_id, starts_at, ends_at),
    KEY idx_availability_search
        (campus_id, delivery_mode, status, starts_at),
    KEY idx_availability_counselor
        (counselor_user_id, starts_at),
    KEY idx_availability_weekly_schedule (weekly_schedule_id),

    CONSTRAINT fk_availability_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_availability_campus
        FOREIGN KEY (campus_id)
        REFERENCES campuses (campus_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_availability_weekly_schedule
        FOREIGN KEY (weekly_schedule_id)
        REFERENCES counselor_weekly_schedules (weekly_schedule_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_availability_time
        CHECK (ends_at > starts_at),

    CONSTRAINT chk_availability_status
        CHECK (status IN ('AVAILABLE', 'RESERVED')),

    CONSTRAINT chk_availability_delivery_mode
        CHECK (delivery_mode IN ('ONLINE', 'FACE_TO_FACE', 'BOTH'))
) ENGINE=InnoDB;

-- conversation_id receives its FK after conversations exists.
CREATE TABLE appointments (
    appointment_id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id                     BIGINT UNSIGNED NOT NULL,
    counselor_user_id                   BIGINT UNSIGNED NOT NULL,
    availability_slot_id                BIGINT UNSIGNED NOT NULL,
    appointment_mode                    VARCHAR(32) NOT NULL,
    concern_category                    VARCHAR(100) NOT NULL,
    concern_details                     VARCHAR(1000) NULL,
    meeting_location                    VARCHAR(255) NULL,
    conversation_id                     BIGINT UNSIGNED NULL,
    status                              VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    active_reservation_slot_id          BIGINT UNSIGNED
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('PENDING', 'CONFIRMED')
                THEN availability_slot_id
                ELSE NULL
            END
        ) STORED,
    rejection_note                      VARCHAR(500) NULL,
    student_reminder_dispatched_at      DATETIME(6) NULL,
    counselor_reminder_dispatched_at    DATETIME(6) NULL,
    created_at                          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                                     ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (appointment_id),
    UNIQUE KEY uq_appointments_active_slot (active_reservation_slot_id),
    UNIQUE KEY uq_appointments_conversation (conversation_id),
    UNIQUE KEY uq_appointments_identity
        (appointment_id, student_user_id, counselor_user_id),
    KEY idx_appointments_student
        (student_user_id, status, created_at),
    KEY idx_appointments_counselor
        (counselor_user_id, status, created_at),
    KEY idx_appointments_slot_status
        (availability_slot_id, status),
    KEY idx_appointments_online_session
        (appointment_mode, status, conversation_id),

    CONSTRAINT fk_appointments_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_appointments_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_appointments_slot
        FOREIGN KEY (availability_slot_id)
        REFERENCES availability_slots (slot_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_appointments_status
        CHECK (
            status IN (
                'PENDING',
                'CONFIRMED',
                'COMPLETED',
                'CANCELLED',
                'REJECTED',
                'NO_SHOW'
            )
        ),

    CONSTRAINT chk_appointments_mode
        CHECK (appointment_mode IN ('ONLINE', 'FACE_TO_FACE')),

    CONSTRAINT chk_appointments_location_shape
        CHECK (
            (appointment_mode = 'ONLINE' AND meeting_location IS NULL)
            OR
            (appointment_mode = 'FACE_TO_FACE' AND meeting_location IS NOT NULL)
        ),

    CONSTRAINT chk_appointments_concern_category
        CHECK (CHAR_LENGTH(TRIM(concern_category)) > 0)
) ENGINE=InnoDB;

-- ============================================================================
-- 5. SCHEDULED TEXT MESSAGING
-- ============================================================================

CREATE TABLE conversations (
    conversation_id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id           BIGINT UNSIGNED NOT NULL,
    counselor_user_id         BIGINT UNSIGNED NOT NULL,
    appointment_id            BIGINT UNSIGNED NULL,
    conversation_type         VARCHAR(32) NOT NULL DEFAULT 'GENERAL',
    status                    VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    started_at                DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    student_joined_at         DATETIME(6) NULL,
    counselor_joined_at       DATETIME(6) NULL,
    closed_at                 DATETIME(6) NULL,
    closure_reason            VARCHAR(32) NULL,
    messages_purged_at        DATETIME(6) NULL,
    last_sequence_number      BIGINT UNSIGNED NOT NULL DEFAULT 0,

    PRIMARY KEY (conversation_id),
    UNIQUE KEY uq_conversations_appointment (appointment_id),
    KEY idx_conversations_student
        (student_user_id, status, started_at),
    KEY idx_conversations_counselor
        (counselor_user_id, status, started_at),
    KEY idx_conversations_retention
        (status, closed_at, messages_purged_at),

    CONSTRAINT fk_conversations_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_conversations_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_conversations_appointment
        FOREIGN KEY (appointment_id)
        REFERENCES appointments (appointment_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_conversations_status
        CHECK (status IN ('OPEN', 'CLOSED')),

    CONSTRAINT chk_conversations_type
        CHECK (conversation_type IN ('GENERAL', 'APPOINTMENT', 'SOS')),

    CONSTRAINT chk_conversations_lifecycle
        CHECK (
            (status = 'OPEN'
                AND closed_at IS NULL
                AND messages_purged_at IS NULL)
            OR
            (status = 'CLOSED'
                AND closed_at IS NOT NULL
                AND (
                    messages_purged_at IS NULL
                    OR messages_purged_at >= closed_at
                ))
        )
) ENGINE=InnoDB;

ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations (conversation_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT;

CREATE TABLE messages (
    message_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    conversation_id       BIGINT UNSIGNED NOT NULL,
    sender_user_id        BIGINT UNSIGNED NOT NULL,
    client_message_id     VARCHAR(100) NULL,
    sequence_number       BIGINT UNSIGNED NOT NULL,
    body                  TEXT NOT NULL,
    sent_at               DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (message_id),
    UNIQUE KEY uq_messages_client_id
        (conversation_id, client_message_id),
    UNIQUE KEY uq_messages_sequence
        (conversation_id, sequence_number),
    KEY idx_messages_conversation_time
        (conversation_id, sent_at),
    KEY idx_messages_sender (sender_user_id, sent_at),

    CONSTRAINT fk_messages_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations (conversation_id)
        ON DELETE CASCADE
        ON UPDATE RESTRICT,

    CONSTRAINT fk_messages_sender
        FOREIGN KEY (sender_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_messages_body
        CHECK (CHAR_LENGTH(body) BETWEEN 1 AND 4000)
) ENGINE=InnoDB;

-- ============================================================================
-- 6. COUNSELING SESSION RECORDS AND ASSESSMENTS
-- ============================================================================

CREATE TABLE counseling_sessions (
    counseling_session_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    appointment_id                 BIGINT UNSIGNED NOT NULL,
    student_user_id                BIGINT UNSIGNED NOT NULL,
    assigned_counselor_user_id     BIGINT UNSIGNED NOT NULL,
    status                         VARCHAR(40) NOT NULL DEFAULT 'SCHEDULED',
    started_at                     DATETIME(6) NULL,
    ended_at                       DATETIME(6) NULL,
    finalized_at                   DATETIME(6) NULL,
    created_at                     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                                 ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (counseling_session_id),
    UNIQUE KEY uq_counseling_sessions_appointment (appointment_id),
    KEY idx_counseling_sessions_student_history
        (student_user_id, status, finalized_at),
    KEY idx_counseling_sessions_counselor_queue
        (assigned_counselor_user_id, status, created_at),

    CONSTRAINT fk_counseling_sessions_appointment_identity
        FOREIGN KEY (appointment_id, student_user_id, assigned_counselor_user_id)
        REFERENCES appointments
            (appointment_id, student_user_id, counselor_user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_counseling_sessions_status
        CHECK (
            status IN (
                'SCHEDULED',
                'IN_PROGRESS',
                'ENDED',
                'DOCUMENTATION_PENDING',
                'FINALIZED'
            )
        ),

    CONSTRAINT chk_counseling_sessions_timeline
        CHECK (
            (started_at IS NULL OR started_at >= created_at)
            AND (ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at))
            AND (finalized_at IS NULL OR (ended_at IS NOT NULL AND finalized_at >= ended_at))
        )
) ENGINE=InnoDB;

-- Private notepad entries. Never return these rows to Students or Superadmin.
CREATE TABLE counselor_session_notes (
    counselor_session_note_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counseling_session_id          BIGINT UNSIGNED NOT NULL,
    authored_by_counselor_user_id  BIGINT UNSIGNED NOT NULL,
    note_body                      LONGTEXT NOT NULL,
    created_at                     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                                 ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (counselor_session_note_id),
    KEY idx_counselor_session_notes_session
        (counseling_session_id, created_at),
    KEY idx_counselor_session_notes_author
        (authored_by_counselor_user_id, created_at),

    CONSTRAINT fk_counselor_session_notes_session
        FOREIGN KEY (counseling_session_id)
        REFERENCES counseling_sessions (counseling_session_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_counselor_session_notes_author
        FOREIGN KEY (authored_by_counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_counselor_session_notes_body
        CHECK (CHAR_LENGTH(TRIM(note_body)) > 0)
) ENGINE=InnoDB;

CREATE TABLE session_assessments (
    session_assessment_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counseling_session_id          BIGINT UNSIGNED NOT NULL,
    authored_by_counselor_user_id  BIGINT UNSIGNED NOT NULL,
    status                         VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    assessment_summary             LONGTEXT NULL,
    clinical_impression            LONGTEXT NULL,
    recommendations                LONGTEXT NULL,
    follow_up_plan                 LONGTEXT NULL,
    finalized_at                   DATETIME(6) NULL,
    created_at                     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                                 ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (session_assessment_id),
    UNIQUE KEY uq_session_assessments_session (counseling_session_id),
    KEY idx_session_assessments_author
        (authored_by_counselor_user_id, status, created_at),
    KEY idx_session_assessments_finalized
        (status, finalized_at),

    CONSTRAINT fk_session_assessments_session
        FOREIGN KEY (counseling_session_id)
        REFERENCES counseling_sessions (counseling_session_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_session_assessments_author
        FOREIGN KEY (authored_by_counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_session_assessments_status
        CHECK (status IN ('DRAFT', 'FINALIZED')),

    CONSTRAINT chk_session_assessments_finalization
        CHECK (
            (status = 'DRAFT' AND finalized_at IS NULL)
            OR
            (status = 'FINALIZED' AND finalized_at IS NOT NULL)
        ),

    CONSTRAINT chk_session_assessments_summary
        CHECK (
            status = 'DRAFT'
            OR (
                status = 'FINALIZED'
                AND assessment_summary IS NOT NULL
                AND CHAR_LENGTH(TRIM(assessment_summary)) > 0
            )
        )
) ENGINE=InnoDB;

CREATE TABLE assessment_correction_requests (
    correction_request_id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_assessment_id               BIGINT UNSIGNED NOT NULL,
    requested_by_student_user_id        BIGINT UNSIGNED NOT NULL,
    routed_by_superadmin_user_id        BIGINT UNSIGNED NULL,
    decided_by_counselor_user_id        BIGINT UNSIGNED NULL,
    status                              VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    request_reason                      VARCHAR(2000) NOT NULL,
    decision_note                       VARCHAR(2000) NULL,
    requested_at                        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    routed_at                           DATETIME(6) NULL,
    resolved_at                         DATETIME(6) NULL,

    PRIMARY KEY (correction_request_id),
    KEY idx_correction_requests_assessment
        (session_assessment_id, status, requested_at),
    KEY idx_correction_requests_student
        (requested_by_student_user_id, status, requested_at),
    KEY idx_correction_requests_queue
        (status, requested_at),

    CONSTRAINT fk_correction_requests_assessment
        FOREIGN KEY (session_assessment_id)
        REFERENCES session_assessments (session_assessment_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_correction_requests_student
        FOREIGN KEY (requested_by_student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_correction_requests_router
        FOREIGN KEY (routed_by_superadmin_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT fk_correction_requests_decider
        FOREIGN KEY (decided_by_counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT chk_correction_requests_status
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'APPLIED')),

    CONSTRAINT chk_correction_requests_lifecycle
        CHECK (
            (status = 'PENDING' AND resolved_at IS NULL)
            OR
            (status IN ('APPROVED', 'REJECTED', 'APPLIED')
                AND resolved_at IS NOT NULL)
        ),

    CONSTRAINT chk_correction_requests_reason
        CHECK (CHAR_LENGTH(TRIM(request_reason)) > 0)
) ENGINE=InnoDB;

-- Append-only: this table intentionally has no updated_at column.
CREATE TABLE assessment_amendments (
    assessment_amendment_id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_assessment_id                BIGINT UNSIGNED NOT NULL,
    correction_request_id                BIGINT UNSIGNED NULL,
    authored_by_counselor_user_id        BIGINT UNSIGNED NOT NULL,
    amendment_text                       LONGTEXT NOT NULL,
    amendment_reason                     VARCHAR(1000) NOT NULL,
    created_at                           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (assessment_amendment_id),
    UNIQUE KEY uq_assessment_amendments_request (correction_request_id),
    KEY idx_assessment_amendments_assessment
        (session_assessment_id, created_at),
    KEY idx_assessment_amendments_author
        (authored_by_counselor_user_id, created_at),

    CONSTRAINT fk_assessment_amendments_assessment
        FOREIGN KEY (session_assessment_id)
        REFERENCES session_assessments (session_assessment_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_assessment_amendments_request
        FOREIGN KEY (correction_request_id)
        REFERENCES assessment_correction_requests (correction_request_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_assessment_amendments_author
        FOREIGN KEY (authored_by_counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_assessment_amendments_text
        CHECK (CHAR_LENGTH(TRIM(amendment_text)) > 0),

    CONSTRAINT chk_assessment_amendments_reason
        CHECK (CHAR_LENGTH(TRIM(amendment_reason)) > 0)
) ENGINE=InnoDB;

-- ============================================================================
-- 7. AUDIO/VIDEO CALL METADATA (NO MEDIA CONTENT)
-- ============================================================================

CREATE TABLE call_sessions (
    call_session_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counseling_session_id      BIGINT UNSIGNED NOT NULL,
    status                     VARCHAR(32) NOT NULL DEFAULT 'WAITING',
    student_joined_at          DATETIME(6) NULL,
    counselor_joined_at        DATETIME(6) NULL,
    started_at                 DATETIME(6) NULL,
    ended_at                   DATETIME(6) NULL,
    ended_by_user_id           BIGINT UNSIGNED NULL,
    end_reason                 VARCHAR(100) NULL,
    created_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (call_session_id),
    UNIQUE KEY uq_call_sessions_counseling_session (counseling_session_id),
    KEY idx_call_sessions_status (status, created_at),
    KEY idx_call_sessions_ended_by (ended_by_user_id),

    CONSTRAINT fk_call_sessions_counseling_session
        FOREIGN KEY (counseling_session_id)
        REFERENCES counseling_sessions (counseling_session_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_call_sessions_ended_by
        FOREIGN KEY (ended_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT chk_call_sessions_status
        CHECK (status IN ('WAITING', 'ACTIVE', 'ENDED', 'FAILED')),

    CONSTRAINT chk_call_sessions_timeline
        CHECK (
            (started_at IS NULL OR started_at >= created_at)
            AND (ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at))
        )
) ENGINE=InnoDB;

-- ============================================================================
-- 8. PRIVATE CLINICAL DOCUMENT METADATA
-- ============================================================================

CREATE TABLE clinical_documents (
    clinical_document_id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id             BIGINT UNSIGNED NOT NULL,
    counseling_session_id       BIGINT UNSIGNED NULL,
    uploaded_by_user_id         BIGINT UNSIGNED NOT NULL,
    document_type               VARCHAR(32) NOT NULL,
    original_filename           VARCHAR(255) NOT NULL,
    storage_key                 VARCHAR(512) NOT NULL,
    mime_type                   VARCHAR(100) NOT NULL,
    size_bytes                  BIGINT UNSIGNED NOT NULL,
    sha256_hash                 BINARY(32) NOT NULL,
    storage_state               VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
    uploaded_at                 DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    deleted_at                  DATETIME(6) NULL,

    PRIMARY KEY (clinical_document_id),
    UNIQUE KEY uq_clinical_documents_storage_key (storage_key),
    KEY idx_clinical_documents_student
        (student_user_id, document_type, uploaded_at),
    KEY idx_clinical_documents_session
        (counseling_session_id, uploaded_at),
    KEY idx_clinical_documents_uploader
        (uploaded_by_user_id, uploaded_at),
    KEY idx_clinical_documents_cleanup
        (storage_state, deleted_at),

    CONSTRAINT fk_clinical_documents_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_clinical_documents_session
        FOREIGN KEY (counseling_session_id)
        REFERENCES counseling_sessions (counseling_session_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_clinical_documents_uploader
        FOREIGN KEY (uploaded_by_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_clinical_documents_type
        CHECK (
            document_type IN (
                'REFERRAL',
                'DIAGNOSIS',
                'PRESCRIPTION',
                'OTHER'
            )
        ),

    CONSTRAINT chk_clinical_documents_size
        CHECK (size_bytes > 0),

    CONSTRAINT chk_clinical_documents_storage_state
        CHECK (
            storage_state IN (
                'AVAILABLE',
                'QUARANTINED',
                'DELETION_PENDING',
                'DELETION_FAILED'
            )
        )
) ENGINE=InnoDB;

-- ============================================================================
-- 9. SOS TRIAGE
-- ============================================================================

CREATE TABLE sos_cases (
    sos_case_id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id                BIGINT UNSIGNED NOT NULL,
    assigned_counselor_user_id     BIGINT UNSIGNED NULL,
    conversation_id                BIGINT UNSIGNED NULL,
    instrument_version             VARCHAR(50) NOT NULL,
    urgency_result_code            VARCHAR(50) NULL,
    status                         VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    submitted_at                   DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    responded_at                   DATETIME(6) NULL,
    closed_at                      DATETIME(6) NULL,

    PRIMARY KEY (sos_case_id),
    UNIQUE KEY uq_sos_cases_conversation (conversation_id),
    KEY idx_sos_cases_student
        (student_user_id, status, submitted_at),
    KEY idx_sos_cases_counselor
        (assigned_counselor_user_id, status, submitted_at),

    CONSTRAINT fk_sos_cases_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_sos_cases_counselor
        FOREIGN KEY (assigned_counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT fk_sos_cases_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations (conversation_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT chk_sos_cases_status
        CHECK (status IN ('OPEN', 'RESPONDED', 'CLOSED')),

    CONSTRAINT chk_sos_cases_lifecycle
        CHECK (
            (status = 'OPEN'
                AND responded_at IS NULL
                AND closed_at IS NULL)
            OR
            (status = 'RESPONDED'
                AND responded_at IS NOT NULL
                AND closed_at IS NULL)
            OR
            (status = 'CLOSED'
                AND responded_at IS NOT NULL
                AND closed_at IS NOT NULL
                AND closed_at >= responded_at)
        )
) ENGINE=InnoDB;

CREATE TABLE sos_responses (
    sos_case_id        BIGINT UNSIGNED NOT NULL,
    question_key       VARCHAR(100) NOT NULL,
    answer_value       VARCHAR(255) NOT NULL,

    PRIMARY KEY (sos_case_id, question_key),

    CONSTRAINT fk_sos_responses_case
        FOREIGN KEY (sos_case_id)
        REFERENCES sos_cases (sos_case_id)
        ON DELETE CASCADE
        ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- ============================================================================
-- 10. LIGHTWEIGHT CONTENT AND EMERGENCY CONTACTS
-- ============================================================================

CREATE TABLE content_items (
    content_id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    content_type           VARCHAR(32) NOT NULL,
    content_key            VARCHAR(150) NULL,
    title                  VARCHAR(500) NULL,
    body                   LONGTEXT NOT NULL,
    is_published           BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_user_id     BIGINT UNSIGNED NULL,
    updated_by_user_id     BIGINT UNSIGNED NULL,
    created_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (content_id),
    UNIQUE KEY uq_content_items_key (content_key),
    KEY idx_content_items_type_published
        (content_type, is_published),
    KEY idx_content_items_created_by (created_by_user_id),
    KEY idx_content_items_updated_by (updated_by_user_id),

    CONSTRAINT fk_content_items_creator
        FOREIGN KEY (created_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT fk_content_items_updater
        FOREIGN KEY (updated_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,

    CONSTRAINT chk_content_items_type
        CHECK (content_type IN ('CMS_BLOCK', 'FAQ', 'ANNOUNCEMENT'))
) ENGINE=InnoDB;

CREATE TABLE emergency_contacts (
    contact_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name               VARCHAR(200) NOT NULL,
    contact_number     VARCHAR(100) NOT NULL,
    description        VARCHAR(500) NULL,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    display_order      INT UNSIGNED NOT NULL DEFAULT 0,

    PRIMARY KEY (contact_id),
    KEY idx_emergency_contacts_active (is_active, display_order)
) ENGINE=InnoDB;

-- ============================================================================
-- 11. AUDIT AND OPERATIONAL EVENTS
-- ============================================================================

CREATE TABLE audit_events (
    audit_event_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_user_id      BIGINT UNSIGNED NULL,
    event_type         VARCHAR(100) NOT NULL,
    target_type        VARCHAR(100) NOT NULL,
    target_id          BIGINT UNSIGNED NULL,
    outcome            VARCHAR(32) NOT NULL,
    metadata_json      JSON NULL,
    occurred_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (audit_event_id),
    KEY idx_audit_events_actor
        (actor_user_id, occurred_at),
    KEY idx_audit_events_target
        (target_type, target_id, occurred_at),
    KEY idx_audit_events_type
        (event_type, occurred_at),

    CONSTRAINT fk_audit_events_actor
        FOREIGN KEY (actor_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- ============================================================================
-- APPLICATION-ENFORCED RULES
-- ============================================================================
-- MySQL cannot enforce role membership, cross-row overlap, or every cross-table
-- lifecycle safely. FastAPI services and automated tests must enforce:
--
-- 1. users.email and student_profiles.student_number are alternative Student
--    login identifiers; identifier collisions are rejected deterministically.
-- 2. Only STUDENT users may own student_profiles and cor_screenings.
-- 3. A Student may have at most one active COR screening at a time; concurrent
--    upload and confirmation requests must be serialized by the service.
-- 4. COR format/OCR/barcode screening does not prove University issuance.
--    The service selects barcode expectations by approved template version.
--    Missing, unreadable, invalid, or inconsistent required barcode results,
--    and scores below approved thresholds, must request resubmission.
--    Raw decoded barcode payloads are never persisted or logged.
-- 5. Only a Student may confirm their extracted COR fields. PASSED screening
--    atomically updates users/student_profiles and enrollment validity.
-- 6. Only COUNSELOR users may own schedules, slots, appointments as Counselor,
--    session notes, assessments, amendments, calls, and assigned case access.
-- 7. SUPERADMIN manages accounts, reference configuration, operational audit,
--    and correction routing, but has no default counseling-content access.
-- 8. Active Counselor weekly periods and availability blocks may not overlap
--    prohibited periods. Blocks never silently alter existing appointments.
-- 9. Booking locks/revalidates the slot, selected mode, campus location, both
--    participants, and concern fields before atomically reserving the slot.
-- 10. Appointment and conversation participants must match. APPOINTMENT chat is
--    allowed only for confirmed ONLINE appointments in the approved window.
-- 11. counseling_sessions participant columns must remain the appointment's
--     participants. The assigned Counselor alone changes its clinical state.
-- 12. Counselor session notes are never returned to Students or Superadmin.
-- 13. FINALIZED session_assessments are immutable. Corrections create an
--     append-only assessment_amendments row; they never overwrite the original.
-- 14. Students may read only their own FINALIZED assessments and amendments.
-- 15. Clinical-document bytes remain outside MySQL/public paths. Access checks
--     bind the Student, uploader, assigned Counselor, and optional session.
-- 16. call_sessions store lifecycle metadata only. WebRTC SDP, ICE credentials,
--     audio/video, recordings, screenshots, transcripts, and summaries are not
--     persisted in this schema.
-- 17. AI-assisted observation is opt-in, non-diagnostic, session-only, and has
--     no table. It never changes SOS results or durable assessments automatically.
-- 18. Message bodies are purged 30 days after conversation closure under the
--     current ADR; final assessments remain separate durable records.
-- 19. Audit metadata must never copy concern text, messages, notes, assessment
--     bodies, SOS answers, COR contents, clinical-file contents, or call media.
--
-- No production retention period for assessments/clinical documents is encoded
-- because ADR-P12 remains pending. The current barcode fields support decoding
-- and internal consistency only; authoritative University verification remains
-- pending under ADR-P10.
-- ============================================================================
