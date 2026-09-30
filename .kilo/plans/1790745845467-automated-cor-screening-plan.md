# Plan — Automated COR Screening (RegistrationWithMachineLearning integration)

Status: READY FOR APPROVAL (HIGH risk — boundary + schema change)
Scope: backend + frontend, one deliverable
Source artifact: `RegistrationWithMachineLearning/` (standalone prototype, target `counselconnect_v5`)

## Goal

Replace the human COR review loop with automated on-upload screening (format match + OCR extraction + embedded-barcode check) and **student self-confirmation** that activates the account. Integrate this into the existing modular monolith, canonical MySQL schema, and 3-role model.

## Locked decisions

1. **Fully automated self-confirmation.** Screening result + student confirmation activates the account. No human approval step.
2. **Keep the 3 canonical roles** (`STUDENT`, `GUIDANCE_STAFF`, `COUNSELOR`). Do **not** adopt v5's `SUPERADMIN`.
3. **COR is the source of truth.** Student submits email + password + COR only; OCR/barcode extract student number, name, campus, program, year, section; student reviews/confirms them.
4. **Reference data integrity.** Extracted campus/program must match an existing active row; on no match the confirm screen shows a selector of existing campuses/programs. Never auto-create campuses/programs.
5. **New tables `cor_screenings` + `cor_screening_files`** exactly per v5 reference SQL, added via Alembic. Retire `enrollment_verifications` as an active path (keep table/rows as legacy; do not drop yet).
6. **Remove the human-review path entirely**: pending/history/approve/reject/assign endpoints, reviewer console UI, and their tests.
7. **Synchronous in-request screening.** External binaries via configurable paths (`pdftotext`, `pdftoppm`, `tesseract`) plus `zxing-cpp` + `Pillow`. If a dependency is missing/fails, fail closed (no auto-activation).
8. **Auto-activate only when ALL pass**: valid PDF, format score ≥ threshold, extraction confidence ≥ threshold, barcode status `DECODED` and payload matches extracted student number, student number unique and matches strict UCC pattern.
9. **Student number format**: strict UCC pattern, e.g. `20231234-A`.
10. **Guidance Staff**: keep role (login only) with no COR duty; amend ADR-003.

## Mandatory governance steps (do first)

- **T1. Write a new ADR** in `.ai/DECISIONS.md` that:
  - supersedes ADR-024's human-review requirement and ADR-020/ADR-003's Guidance Staff COR-review duty,
  - records automated screening + self-confirmation, its status vocabulary, and the **residual risk that document-only screening cannot prove University issuance** (v5 notes this explicitly; authoritative barcode verification remains pending),
  - sets approval authority for this change (must be explicitly approved by the human owner before code).
- **T2. Update the owning contracts**: `docs/REGISTRATION_VERIFICATION.md`, `docs/API_CONTRACT.md`, `.ai/NAMING_CONVENTIONS.md` (add screening states), `.ai/CONTEXT_MAP.md` (registration route → new cleanup/module path), and affected requirement/project references. Follow `docs/MARKDOWN_UPDATE_GUIDE.txt`.

## Backend tasks

- **B1. Migration (Alembic)**: create `cor_screenings` and `cor_screening_files` with the exact columns, indexes, FKs, and CHECKs from `RegistrationWithMachineLearning/reference/CounselConnect_Target_Database_v5.sql` (lines 206–353). Do not modify the v4.1 baseline SQL. Keep `enrollment_verifications` untouched.
  - Storage: reuse `COUNSELCONNECT_COR_STORAGE_ROOT` private store; COR bytes never in MySQL.
- **B2. New module `backend/app/modules/cor_screening/`** (models, repository, service, schemas, screening engine, cleanup, router):
  - `models.py`: ORM mirrors of the two new tables (register in `app/db/base.py`).
  - `screening.py` (pure engine, ported and de-duplicated from prototype `screen_document`/`outcome`):
    - text extraction (`pdftotext -layout`), OCR fallback (`pdftoppm` + `tesseract`), field parsing, `zxingcpp` barcode decode.
    - Fix prototype defects: barcode `payload_hash` must be SHA-256 of the **payload**, not the PDF; **never** print/log the raw payload or raw OCR text.
    - Remove `find_or_create_campus` / `find_or_create_program`; return unmatched names for the confirm selector instead.
  - `service.py`:
    - `submit(student_user_id, content, filename)` → store file, run screening, persist `cor_screenings` + file row, set status `AWAITING_CONFIRMATION` or `NEEDS_RESUBMISSION`, audit `cor_screening_submitted`; never auto-activate here.
    - `confirm(student, payload)` → in one locked transaction: validate required fields, uniqueness of student number, resolve `campus_id`/`program_id` to active rows, create/update `student_profiles`, set `users.account_status='ACTIVE'` + `valid_until` (default 12 months), set screening `PASSED`/`confirmed_at`, delete COR bytes; commit before deletion.
    - `resubmit(student, content, filename)` → replace open screening, re-screen; keep original 7-day deadline semantics.
    - `list_for_counselor(actor, filters)` → read-only screening/audit view (COUNSELOR only; GUIDANCE_STAFF allowed read of assigned rows only if an assignment exists — none by default).
    - Reuse existing `_validate_pdf` (PDF magic, 10 MB per ADR-024), lock ordering (student then screening), commit-then-delete, and cleanup-failure retry pattern.
  - `cleanup.py`: port the existing worker to the new tables — expire stale screenings, delete due/mismatched files, retry `FAILED` cleanup, reconcile `.pending` markers. Update `app/main.py` lifespan import.
  - `schemas.py` + `router.py`:
    - `POST /accounts/register/student-with-cor` (multipart: `email`, `password`, `file`) → account `PENDING_VERIFICATION` + screening; returns screening status + extracted fields + unmatched campus/program names.
    - `GET /accounts/registration/screening` (current student) — status/details for the dashboard/confirm screen.
    - `POST /accounts/registration/confirm` (confirmed fields + `campus_id`/`program_id`) → account activation.
    - `POST /accounts/registration/resubmit` (multipart `file`).
    - Counselor read-only list endpoint under `/cor-screenings`.
    - Follow `.ai/NAMING_CONVENTIONS.md`; snake_case DTOs, SCREAMING_SNAKE_CASE enums, stable error codes.
- **B3. Remove the old human-review path**: delete `enrollment_verification` router/service/repository/models/schemas from the active router (`app/modules_router.py`), remove `POST /accounts/register/student` (bare, no-COR) or keep it creating `PENDING_VERIFICATION` only — **recommend removing** since COR is now mandatory. Keep `enrollment_verifications` table only as legacy history.
- **B4. Config** (`app/config.py`): add `cor_screening_enabled` (default true; when false the register endpoint fails closed with a clear error, never auto-activates), `cor_format_pass_score` (default 0.60), `cor_extraction_pass_score` (default 0.60), `cor_template_version` (default `ucc-registration-v1`), and binary paths `pdftotext_path`/`pdftoppm_path`/`tesseract_path`. No hardcoded credentials/paths.
- **B5. Dependencies**: add `zxing-cpp`, `Pillow` to `backend/requirements.txt`. Document the OS-level poppler/Tesseract requirement (binary paths configurable).

## Frontend tasks

- **F1. `frontend/src/pages/RegisterPage.jsx` + `frontend/src/features/accounts/useRegistration.js`**: reduce to email + password + COR upload; remove name/student-number/campus/program/year/section inputs.
- **F2. New confirm screen** (route + page, e.g. `frontend/src/pages/student/ConfirmDetailsPage.jsx` + hook): show extracted fields; allow campus/program pick from existing lists when unmatched; Confirm or Reject(re-submit). Reject → resubmission.
- **F3. New resubmission screen** for `NEEDS_RESUBMISSION`/`FAILED`, mirroring the prototype's `/resubmit` UX but with existing error codes.
- **F4. Remove reviewer console**: delete `frontend/src/pages/ReviewerPage.jsx`, `frontend/src/features/enrollment/useReviewerConsole.js`, related routes/nav/tests. Keep/repurpose a Counselor read-only screening list if useful.
- **F5. API client + tests**: update `useRegistration`, route wiring, and frontend tests; add tests for register → confirm activation, unmatched campus selection, and resubmission.

## Tests (required — HIGH risk)

Backend (unit): outcome matrix (pass, low format, low extraction, missing fields, unreadable, barcode NOT_FOUND/UNREADABLE/INVALID_FORMAT/MISMATCH); strict student-number rejection; **barcode raw payload never persisted/logged**; no auto-create of campus/program; missing-binary fail-safe (no activation); uniqueness conflicts; confirm activation sets `ACTIVE` + `valid_until` + deletes COR; TTL expiry + cleanup retry; unauthorized screening read.
Backend (integration/MySQL): full register → screen → confirm lifecycle; concurrent confirm upload/confirm serialization; legacy `enrollment_verifications` untouched.
Frontend: register submit, confirm success/selection, resubmit, reviewer-console removal sanity.

## Validation commands

- Backend: `pytest` from `backend/` (note: MySQL-dependent tests are skipped unless `COUNSELCONNECT_TEST_DATABASE_URL` is set — configure it to actually verify schema/flow).
- `alembic upgrade head` against a scratch MySQL 8.4 database; confirm `cor_screenings`/`cor_screening_files` and that the migration is reversible.
- Frontend: project test suite + `npm run build`.
- Regenerate `contracts/openapi.json` if it exists; run any OpenAPI snapshot check.
- `git diff --check`.
- **HIGH risk → fresh read-only review before acceptance** (per `.kilo/rules/01-workflow.md`): authorization, COR privacy/deletion, state transitions, dependency-failure path, migration/retention, and payload-logging.

## Risks / limitations

- **Spoofability (accepted, must be documented)**: barcode/value checks are self-consistent only; a crafted PDF can pass. No authoritative registrar verification exists. Compensating controls kept: strict pattern, uniqueness, audit, `valid_until` renewal.
- **Ops dependency**: poppler/Tesseract must be installed and reachable; misconfiguration fails closed (denies activation) — monitor screening failures.
- **Guidance Staff** have no COR function after this change (role retained; ADR-003 amended).
- Deleting `enrollment_verifications` is deferred; two DECISION records (legacy table + new screening) coexist until a later cleanup migration.
- The `RegistrationWithMachineLearning/` prototype must stay outside `backend/`; archive/delete it after the port.

## Open items (recommend defaults, confirm during T1)

- Keep an "activation" notification email on confirm? Recommend yes, reusing `app/core/notifications.py`.
- Remove the bare `POST /accounts/register/student` endpoint? Recommend yes.
- Feature-flag default: recommend `cor_screening_enabled=true`; disable is an ops kill-switch that blocks new registrations (fails closed).

## Execution hand-off

No source changes are made by this plan. Implementation requires switching to a Code agent. Order: T1 → T2 → B1 → B2 → B3/B4/B5 → F1–F5 → tests → validation → fresh review.
