-- ============================================================
-- CounselConnect Initial Database Schema v4
-- Target: MySQL 8.4 LTS
-- Character set: utf8mb4
--
-- Source priority:
-- 1. Current CounselConnect DFD
-- 2. Current CounselConnect flowchart
-- 3. Current project database and naming contracts where the
--    diagrams do not define a detail
--
-- v4 alignment summary:
-- - Replaces the removed ADMINISTRATOR role with GUIDANCE_STAFF.
-- - Stores one optional Guidance Staff assignment per verification.
-- - Enforces diagram-defined verification, conversation, and SOS lifecycles.
-- - Prevents more than one PENDING/CONFIRMED appointment per slot.
-- - Constrains concrete-slot and resource-acquisition states.
-- - Enforces resource provenance, review, and content-shape boundaries.
-- - Adds counselor-defined ONLINE, FACE_TO_FACE, or BOTH availability.
-- - Stores one Guidance Office location per campus instead of duplicating
--   manually entered locations across availability slots.
-- - Stores the student's selected appointment mode and FTF location snapshot.
-- - Links confirmed online appointments to dedicated Live Chat conversations.
--
-- IMPORTANT PRIVACY BOUNDARIES:
-- 1. COR file CONTENT is NOT stored in MySQL. Only temporary storage
--    references exist in enrollment_verification_files.
-- 2. The Observed Expression Cue from optional local facial-expression
--    recognition is session-only
--    in v1 and is NOT persisted.
-- 3. Raw facial images, video, camera frames, embeddings, and
--    biometric templates are NEVER stored.
-- 4. Full third-party wellness article bodies are NOT mirrored.
-- 5. Chat message bodies are intended for deletion 30 days after
--    the related conversation closes.
--
-- Timestamps are intended to be written/read as UTC by FastAPI.
-- The application connection should also use UTC.
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS counselconnect
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE counselconnect;

-- ============================================================
-- 1. IDENTITY / ACADEMIC LOOKUPS
-- ============================================================

CREATE TABLE IF NOT EXISTS campuses (
    campus_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    campus_name     VARCHAR(150) NOT NULL,
    guidance_office_location VARCHAR(255) NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (campus_id),
    UNIQUE KEY uq_campuses_name (campus_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS departments (
    department_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    department_name     VARCHAR(150) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (department_id),
    UNIQUE KEY uq_departments_name (department_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS programs (
    program_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    department_id    BIGINT UNSIGNED NOT NULL,
    program_code     VARCHAR(50) NOT NULL,
    program_name     VARCHAR(200) NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (program_id),
    UNIQUE KEY uq_programs_code (program_code),
    KEY idx_programs_department (department_id),

    CONSTRAINT fk_programs_department
        FOREIGN KEY (department_id)
        REFERENCES departments (department_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
    user_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email            VARCHAR(320) NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    role_code        VARCHAR(32) NOT NULL,
    account_status   VARCHAR(40) NOT NULL,
    first_name       VARCHAR(100) NOT NULL,
    middle_name      VARCHAR(100) NULL,
    last_name        VARCHAR(100) NOT NULL,
    created_at       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                 ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (user_id),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role_status (role_code, account_status),

    CONSTRAINT chk_users_role
        CHECK (role_code IN ('STUDENT', 'GUIDANCE_STAFF', 'COUNSELOR')),

    CONSTRAINT chk_users_account_status
        CHECK (
            account_status IN (
                'PENDING_VERIFICATION',
                'ACTIVE',
                'VERIFICATION_EXPIRED'
            )
        )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS student_profiles (
    user_id          BIGINT UNSIGNED NOT NULL,
    student_number   VARCHAR(50) NOT NULL,
    campus_id        BIGINT UNSIGNED NOT NULL,
    program_id       BIGINT UNSIGNED NOT NULL,
    year_level       TINYINT UNSIGNED NOT NULL,
    section          VARCHAR(50) NOT NULL,

    PRIMARY KEY (user_id),
    UNIQUE KEY uq_student_profiles_number (student_number),
    KEY idx_student_profiles_campus (campus_id),
    KEY idx_student_profiles_program (program_id),

    CONSTRAINT fk_student_profiles_user
        FOREIGN KEY (user_id)
        REFERENCES users (user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_student_profiles_campus
        FOREIGN KEY (campus_id)
        REFERENCES campuses (campus_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_student_profiles_program
        FOREIGN KEY (program_id)
        REFERENCES programs (program_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 2. ENROLLMENT / COR VERIFICATION
-- ============================================================

CREATE TABLE IF NOT EXISTS enrollment_verifications (
    verification_id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id        BIGINT UNSIGNED NOT NULL,
    status                 VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    submitted_at           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    assigned_guidance_staff_user_id BIGINT UNSIGNED NULL,
    decision_at            DATETIME(6) NULL,
    reviewed_by_user_id    BIGINT UNSIGNED NULL,
    reason_code            VARCHAR(50) NULL,
    reviewer_note          VARCHAR(500) NULL,
    valid_until            DATE NULL,

    PRIMARY KEY (verification_id),
    KEY idx_verifications_student_status
        (student_user_id, status, submitted_at),
    KEY idx_verifications_validity
        (student_user_id, status, valid_until),
    KEY idx_verifications_reviewer
        (reviewed_by_user_id),
    KEY idx_verifications_staff_queue
        (assigned_guidance_staff_user_id, status, submitted_at),

    CONSTRAINT fk_verifications_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_verifications_reviewer
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_verifications_assigned_staff
        FOREIGN KEY (assigned_guidance_staff_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT chk_verifications_status
        CHECK (
            status IN (
                'PENDING',
                'APPROVED',
                'NEEDS_RESUBMISSION',
                'REJECTED',
                'EXPIRED'
            )
        ),

    CONSTRAINT chk_verifications_decision_shape
        CHECK (
            (status = 'PENDING'
                AND decision_at IS NULL
                AND reviewed_by_user_id IS NULL
                AND valid_until IS NULL)
            OR
            (status = 'APPROVED'
                AND decision_at IS NOT NULL
                AND reviewed_by_user_id IS NOT NULL
                AND valid_until IS NOT NULL)
            OR
            (status IN ('NEEDS_RESUBMISSION', 'REJECTED')
                AND decision_at IS NOT NULL
                AND reviewed_by_user_id IS NOT NULL
                AND reason_code IS NOT NULL
                AND valid_until IS NULL)
            OR
            (status = 'EXPIRED'
                AND decision_at IS NULL
                AND reviewed_by_user_id IS NULL
                AND valid_until IS NULL)
        )
) ENGINE=InnoDB;

-- TEMPORARY metadata only.
-- The actual COR file remains in isolated non-public storage.
-- These rows should be deleted once the corresponding file is
-- successfully deleted after approval/rejection/resubmission/expiry.
CREATE TABLE IF NOT EXISTS enrollment_verification_files (
    file_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    verification_id    BIGINT UNSIGNED NOT NULL,
    storage_key        VARCHAR(512) NOT NULL,
    mime_type          VARCHAR(100) NOT NULL,
    size_bytes         BIGINT UNSIGNED NOT NULL,
    expires_at         DATETIME(6) NOT NULL,
    cleanup_state      VARCHAR(32) NOT NULL DEFAULT 'PENDING',

    PRIMARY KEY (file_id),
    UNIQUE KEY uq_verification_files_storage_key (storage_key),
    KEY idx_verification_files_verification (verification_id),
    KEY idx_verification_files_cleanup (cleanup_state, expires_at),

    CONSTRAINT fk_verification_files_verification
        FOREIGN KEY (verification_id)
        REFERENCES enrollment_verifications (verification_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT chk_verification_files_size
        CHECK (size_bytes > 0),

    -- Successful cleanup deletes this metadata row. FAILED rows
    -- remain available for retry/alert without exposing file content.
    CONSTRAINT chk_verification_files_cleanup_state
        CHECK (cleanup_state IN ('PENDING', 'FAILED'))
) ENGINE=InnoDB;

-- ============================================================
-- 3. APPOINTMENT SCHEDULING
-- ============================================================

CREATE TABLE IF NOT EXISTS availability_slots (
    slot_id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    counselor_user_id    BIGINT UNSIGNED NOT NULL,
    campus_id            BIGINT UNSIGNED NOT NULL,
    delivery_mode        VARCHAR(32) NOT NULL,
    starts_at            DATETIME(6) NOT NULL,
    ends_at              DATETIME(6) NOT NULL,
    status               VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
    created_at           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (slot_id),
    UNIQUE KEY uq_availability_slot
        (counselor_user_id, campus_id, starts_at, ends_at),
    KEY idx_availability_search
        (campus_id, delivery_mode, status, starts_at),
    KEY idx_availability_counselor
        (counselor_user_id, starts_at),

    CONSTRAINT fk_availability_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_availability_campus
        FOREIGN KEY (campus_id)
        REFERENCES campuses (campus_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT chk_availability_time
        CHECK (ends_at > starts_at),

    CONSTRAINT chk_availability_status
        CHECK (status IN ('AVAILABLE', 'RESERVED')),

    CONSTRAINT chk_availability_delivery_mode
        CHECK (
            delivery_mode IN ('ONLINE', 'FACE_TO_FACE', 'BOTH')
        )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id         BIGINT UNSIGNED NOT NULL,
    counselor_user_id       BIGINT UNSIGNED NOT NULL,
    availability_slot_id    BIGINT UNSIGNED NOT NULL,
    appointment_mode         VARCHAR(32) NOT NULL,
    -- Snapshot of the approved onsite location. It remains NULL for
    -- online appointments even when the source slot supports BOTH.
    meeting_location         VARCHAR(255) NULL,
    -- Created only for the dedicated scheduled online session.
    -- Its FK is added after conversations is created below.
    conversation_id          BIGINT UNSIGNED NULL,
    status                  VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    -- MySQL permits multiple NULL values in a unique index. This
    -- generated guard therefore allows history for completed/rejected/
    -- cancelled appointments while preventing two active reservations
    -- for the same concrete slot.
    active_reservation_slot_id BIGINT UNSIGNED
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('PENDING', 'CONFIRMED')
                THEN availability_slot_id
                ELSE NULL
            END
        ) STORED,
    rejection_note          VARCHAR(500) NULL,
    created_at              DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at              DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                        ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (appointment_id),
    KEY idx_appointments_student
        (student_user_id, status, created_at),
    KEY idx_appointments_counselor
        (counselor_user_id, status, created_at),
    KEY idx_appointments_slot_status
        (availability_slot_id, status),
    KEY idx_appointments_online_session
        (appointment_mode, status, conversation_id),
    UNIQUE KEY uq_appointments_active_slot
        (active_reservation_slot_id),
    UNIQUE KEY uq_appointments_conversation
        (conversation_id),

    CONSTRAINT fk_appointments_student
        FOREIGN KEY (student_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_appointments_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_appointments_slot
        FOREIGN KEY (availability_slot_id)
        REFERENCES availability_slots (slot_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

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
        CHECK (
            appointment_mode IN ('ONLINE', 'FACE_TO_FACE')
        ),

    CONSTRAINT chk_appointments_location_shape
        CHECK (
            (appointment_mode = 'ONLINE' AND meeting_location IS NULL)
            OR
            (appointment_mode = 'FACE_TO_FACE'
                AND meeting_location IS NOT NULL)
        )
) ENGINE=InnoDB;

-- ============================================================
-- 4. REAL-TIME TEXT MESSAGING
-- ============================================================

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_user_id       BIGINT UNSIGNED NOT NULL,
    counselor_user_id     BIGINT UNSIGNED NULL,
    conversation_type     VARCHAR(32) NOT NULL DEFAULT 'GENERAL',
    status                VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    started_at            DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    closed_at             DATETIME(6) NULL,
    messages_purged_at    DATETIME(6) NULL,

    PRIMARY KEY (conversation_id),
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
        ON UPDATE CASCADE,

    CONSTRAINT fk_conversations_counselor
        FOREIGN KEY (counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT chk_conversations_status
        CHECK (status IN ('OPEN', 'CLOSED')),

    CONSTRAINT chk_conversations_type
        CHECK (
            conversation_type IN ('GENERAL', 'APPOINTMENT', 'SOS')
        ),

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

-- appointments is created first because availability belongs to the
-- scheduling domain. Add this forward relationship after conversations
-- exists. The script remains intended for a fresh database.
ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations (conversation_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS messages (
    message_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    conversation_id       BIGINT UNSIGNED NOT NULL,
    sender_user_id        BIGINT UNSIGNED NOT NULL,
    client_message_id     VARCHAR(100) NULL,
    body                  TEXT NOT NULL,
    sent_at               DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (message_id),
    UNIQUE KEY uq_messages_client_id
        (conversation_id, client_message_id),
    KEY idx_messages_conversation_time
        (conversation_id, sent_at),
    KEY idx_messages_sender
        (sender_user_id, sent_at),

    CONSTRAINT fk_messages_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations (conversation_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_messages_sender
        FOREIGN KEY (sender_user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 5. SOS TRIAGE
-- ============================================================

CREATE TABLE IF NOT EXISTS sos_cases (
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
        ON UPDATE CASCADE,

    CONSTRAINT fk_sos_cases_counselor
        FOREIGN KEY (assigned_counselor_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_sos_cases_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations (conversation_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

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

CREATE TABLE IF NOT EXISTS sos_responses (
    sos_case_id        BIGINT UNSIGNED NOT NULL,
    question_key       VARCHAR(100) NOT NULL,
    answer_value       VARCHAR(255) NOT NULL,

    PRIMARY KEY (sos_case_id, question_key),

    CONSTRAINT fk_sos_responses_case
        FOREIGN KEY (sos_case_id)
        REFERENCES sos_cases (sos_case_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 6. WELLNESS RESOURCE DISCOVERY / LIBRARY
-- ============================================================

CREATE TABLE IF NOT EXISTS resource_sources (
    source_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_name          VARCHAR(200) NOT NULL,
    canonical_domain     VARCHAR(255) NOT NULL,
    feed_url             VARCHAR(2048) NULL,
    acquisition_mode     VARCHAR(32) NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                      ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (source_id),
    UNIQUE KEY uq_resource_sources_domain (canonical_domain),

    CONSTRAINT chk_resource_sources_acquisition_mode
        CHECK (
            acquisition_mode IN (
                'RSS',
                'ATOM',
                'STRUCTURED',
                'SCRAPING_FALLBACK'
            )
        )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resource_categories (
    category_id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    category_name      VARCHAR(150) NOT NULL,
    slug               VARCHAR(150) NOT NULL,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (category_id),
    UNIQUE KEY uq_resource_categories_name (category_name),
    UNIQUE KEY uq_resource_categories_slug (slug)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS wellness_resources (
    resource_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    resource_type          VARCHAR(32) NOT NULL,
    source_id              BIGINT UNSIGNED NULL,
    created_by_user_id     BIGINT UNSIGNED NULL,
    title                  VARCHAR(500) NOT NULL,
    summary                TEXT NULL,
    external_url           VARCHAR(2048) NULL,
    content_body           LONGTEXT NULL,
    status                 VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    discovered_at          DATETIME(6) NULL,
    reviewed_by_user_id    BIGINT UNSIGNED NULL,
    reviewed_at            DATETIME(6) NULL,
    published_at           DATETIME(6) NULL,
    created_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                       ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (resource_id),
    KEY idx_wellness_resources_source
        (source_id, status, discovered_at),
    KEY idx_wellness_resources_status
        (status, published_at),
    KEY idx_wellness_resources_creator
        (created_by_user_id),
    KEY idx_wellness_resources_reviewer
        (reviewed_by_user_id),

    CONSTRAINT fk_wellness_resources_source
        FOREIGN KEY (source_id)
        REFERENCES resource_sources (source_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_wellness_resources_creator
        FOREIGN KEY (created_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_wellness_resources_reviewer
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT chk_wellness_resources_type
        CHECK (
            resource_type IN (
                'EXTERNAL_LINK',
                'INTERNAL_ARTICLE',
                'INTERNAL_FILE'
            )
        ),

    CONSTRAINT chk_wellness_resources_status
        CHECK (
            status IN (
                'PENDING',
                'PUBLISHED',
                'REJECTED',
                'DISABLED'
            )
        ),

    -- External discoveries/links store bounded metadata and a canonical
    -- URL, never a mirrored article body. Internal content must not point
    -- to an external publisher URL.
    CONSTRAINT chk_wellness_resources_content_shape
        CHECK (
            (resource_type = 'EXTERNAL_LINK'
                AND external_url IS NOT NULL
                AND content_body IS NULL)
            OR
            (resource_type = 'INTERNAL_ARTICLE'
                AND external_url IS NULL
                AND content_body IS NOT NULL)
            OR
            (resource_type = 'INTERNAL_FILE'
                AND external_url IS NULL
                AND content_body IS NULL)
        ),

    CONSTRAINT chk_wellness_resources_provenance
        CHECK (
            source_id IS NOT NULL
            OR created_by_user_id IS NOT NULL
        ),

    CONSTRAINT chk_wellness_resources_review_state
        CHECK (
            (status = 'PENDING'
                AND published_at IS NULL)
            OR
            (status = 'PUBLISHED'
                AND reviewed_by_user_id IS NOT NULL
                AND reviewed_at IS NOT NULL
                AND published_at IS NOT NULL)
            OR
            (status = 'REJECTED'
                AND reviewed_by_user_id IS NOT NULL
                AND reviewed_at IS NOT NULL
                AND published_at IS NULL)
            OR
            (status = 'DISABLED'
                AND reviewed_by_user_id IS NOT NULL
                AND reviewed_at IS NOT NULL
                AND published_at IS NOT NULL)
        )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resource_files (
    resource_file_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    resource_id           BIGINT UNSIGNED NOT NULL,
    storage_key           VARCHAR(512) NOT NULL,
    original_filename     VARCHAR(255) NOT NULL,
    mime_type             VARCHAR(100) NOT NULL,
    size_bytes            BIGINT UNSIGNED NOT NULL,
    display_order         INT UNSIGNED NOT NULL DEFAULT 0,
    uploaded_at           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (resource_file_id),
    UNIQUE KEY uq_resource_files_storage_key (storage_key),
    KEY idx_resource_files_resource
        (resource_id, display_order),

    CONSTRAINT fk_resource_files_resource
        FOREIGN KEY (resource_id)
        REFERENCES wellness_resources (resource_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT chk_resource_files_size
        CHECK (size_bytes > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS wellness_resource_categories (
    resource_id      BIGINT UNSIGNED NOT NULL,
    category_id      BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (resource_id, category_id),
    KEY idx_resource_category_category (category_id),

    CONSTRAINT fk_resource_category_resource
        FOREIGN KEY (resource_id)
        REFERENCES wellness_resources (resource_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_resource_category_category
        FOREIGN KEY (category_id)
        REFERENCES resource_categories (category_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 7. LIGHTWEIGHT CMS / FAQ / ANNOUNCEMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS content_items (
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
        ON UPDATE CASCADE,

    CONSTRAINT fk_content_items_updater
        FOREIGN KEY (updated_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT chk_content_items_type
        CHECK (content_type IN ('CMS_BLOCK', 'FAQ', 'ANNOUNCEMENT'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name               VARCHAR(200) NOT NULL,
    contact_number     VARCHAR(100) NOT NULL,
    description        VARCHAR(500) NULL,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    display_order      INT UNSIGNED NOT NULL DEFAULT 0,

    PRIMARY KEY (contact_id),
    KEY idx_emergency_contacts_active
        (is_active, display_order)
) ENGINE=InnoDB;

-- ============================================================
-- 8. AUDIT / OPERATIONAL EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_events (
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
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- INITIAL DATABASE NOTES
-- ============================================================

-- No real student, Guidance Staff, or Counselor data is seeded by this file.
-- The initial COUNSELOR account should be created by the
-- development team using the application's password-hashing logic.
--
-- Student login identifier:
--   student_profiles.student_number
--
-- Student email:
--   users.email (personal email)
--
-- Staff login identifier remains an authentication implementation
-- detail; users.email is available for that purpose.
--
-- Validity-based access:
--   An approved enrollment_verifications.valid_until represents
--   current enrollment validity. When the latest approved validity
--   expires, FastAPI should restrict normal student features and
--   require a new COR verification. No graduation-prediction table
--   or database event scheduler is required.
--
-- Message retention:
--   After conversations.closed_at, message bodies should be purged
--   after 30 days by application/scheduled cleanup logic. The
--   conversation metadata may remain.
--
-- SOS response retention:
--   Exact deletion period is intentionally NOT hard-coded here.
--   It is pending counselor/adviser consultation.
--
-- Observed Expression Cue:
--   No table or column exists for it because optional local
--   facial-expression recognition produces session-only Counselor
--   context. It never affects SOS scoring and is never persisted.

-- Diagram-derived application rules that DDL cannot enforce alone:
--   1. assigned_guidance_staff_user_id must reference a user whose
--      role_code is GUIDANCE_STAFF. Guidance Staff may read/decide only
--      assigned verification cases. Counselor access remains subject to
--      authorization and purpose.
--   2. reviewed_by_user_id may be GUIDANCE_STAFF for an assigned case or
--      COUNSELOR for an authorized case.
--   3. Creating a PENDING appointment must lock the selected slot, verify
--      AVAILABLE, verify that appointment_mode is supported by the slot's
--      delivery_mode, and verify that the slot's campus has a configured
--      guidance_office_location for FACE_TO_FACE. When applicable, copy that
--      campus location into appointments.meeting_location as an immutable
--      booking snapshot. Create the appointment and set the slot to RESERVED
--      in one transaction.
--      Rejection/cancellation/rescheduling releases the applicable future
--      slot according to the approved workflow.
--   4. A confirmed ONLINE appointment may create exactly one dedicated
--      APPOINTMENT conversation when its scheduled start is reached. The
--      conversation must contain the same student and counselor as the
--      appointment. FACE_TO_FACE appointments must never receive a linked
--      conversation_id.
--   5. GENERAL Live Chat remains independent from scheduled appointment
--      conversations. SOS conversations use conversation_type = 'SOS'.
--      A conversation must not be linked to both an appointment and SOS case.
--   6. Only the Student and Counselor recorded on an OPEN conversation
--      may exchange messages.
--   7. After 30 days from conversations.closed_at, delete message rows and
--      set messages_purged_at; retain only permitted conversation metadata.
--   8. Only COUNSELOR may publish/reject/disable wellness resources or
--      mutate CMS, announcements, emergency contacts, accounts, staff,
--      academic corrections, and authorized audit views.
