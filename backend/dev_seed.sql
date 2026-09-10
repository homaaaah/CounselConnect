-- CounselConnect development seed data.
-- Run ONCE on a fresh database, after `alembic upgrade head`:
--   mysql -u <your-user> -p counselconnect < backend/dev_seed.sql
-- Safe to re-run for the unique-key rows (campuses/departments/programs/hero block);
-- FAQ/announcement rows may duplicate if run twice.

INSERT INTO campuses (campus_name, guidance_office_location) VALUES
  ('Main Campus', 'Guidance and Counseling Office, 2F Main Building')
  , ('Second Campus', NULL)
ON DUPLICATE KEY UPDATE campus_name = campus_name;

INSERT INTO departments (department_name) VALUES
  ('Department of Student Affairs')
ON DUPLICATE KEY UPDATE department_name = department_name;

INSERT INTO programs (department_id, program_code, program_name) VALUES
  ((SELECT department_id FROM departments WHERE department_name = 'Department of Student Affairs'), 'BSIT-DEV', 'BS Information Technology')
  , ((SELECT department_id FROM departments WHERE department_name = 'Department of Student Affairs'), 'BSED-GEN', 'BS Education (General)')
ON DUPLICATE KEY UPDATE program_code = program_code;

INSERT INTO content_items (content_type, content_key, title, body, is_published) VALUES
  ('CMS_BLOCK', 'landing_hero', 'Guidance and Counseling Services',
   'Book appointments, chat with your guidance counselor, access verified wellness resources, and reach confidential support — all in one place.', 1)
ON DUPLICATE KEY UPDATE content_key = content_key;

INSERT INTO content_items (content_type, content_key, title, body, is_published) VALUES
  ('FAQ', NULL, 'How do I get access to counseling services?',
   'Register with your student details, upload your current COR (Certificate of Registration), and wait for Guidance verification. Once approved, your account becomes active and all services unlock.', 1)
  , ('FAQ', NULL, 'What is a COR and why do I need to upload it?',
   'Your Certificate of Registration is the only accepted proof of current enrollment. It is stored privately and temporarily, and deleted after the verification decision.', 1)
  , ('FAQ', NULL, 'Is my conversation with the counselor private?',
   'Only you and your assigned counselor can see the conversation. Message content is deleted 30 days after the conversation closes.', 1)
  , ('ANNOUNCEMENT', NULL, 'Welcome to CounselConnect',
   'The Guidance and Counseling Office is now online. Register, verify your enrollment, and schedule your first appointment.', 1);

INSERT INTO emergency_contacts (name, contact_number, description, is_active, display_order) VALUES
  ('Guidance and Counseling Office', '(02) 8123-4567', 'Main office, weekdays 8am-5pm', 1, 1)
  , ('Campus Security', '(02) 8123-4568', '24/7 campus security hotline', 1, 2)
  , ('National Mental Health Hotline', '1553', 'Free 24/7 crisis support (DOH)', 1, 3);

-- Dev counselor account (ADR-005: initial staff accounts are developer-created).
-- Password: counselor-dev-2026 (dev only — rotate before any real deployment).
-- Hash below is Argon2id; to regenerate:
--   python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('new'))"
INSERT INTO users (email, password_hash, role_code, account_status, first_name, last_name) VALUES
  ('counselor@ucc.edu.ph',
   '$argon2id$v=19$m=65536,t=3,p=4$43nTlIUufFh8aMcQiWuBeg$sIpNnGlbCkbgOdcdOEN0gpk8beIvUAkjfkVzVtQ+nuI',
   'COUNSELOR', 'ACTIVE', 'Guidance', 'Counselor')
ON DUPLICATE KEY UPDATE email = email;
