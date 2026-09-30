# CounselConnect - Current Task

**Status:** COMPLETE (pending independent review)
**Task:** Implement ADR-029 automated COR screening + Student self-confirmation, replacing the human enrollment-review queue (registration, backend module, migration, frontend, tests, docs).

## Objective

A Student submits email + password + current COR; the backend screens the PDF (format score + OCR extraction + embedded barcode) in-request and the Student confirms the extracted academic fields, which activates the account with `valid_until`. No human approval queue.

## Route

`registration` (`.ai/CONTEXT_MAP.md`) → `docs/REGISTRATION_VERIFICATION.md`, `docs/USER_ROLES.md`, `backend/app/modules/cor_screening/`.

## In scope

- New `cor_screenings` / `cor_screening_files` tables (Alembic `20260930_automated_cor_screening`).
- New `cor_screening` module: screening engine, service, repository, schemas, cleanup worker, router.
- Registration endpoint rewritten to email+password+COR; student confirm/resubmit endpoints.
- Removal of the human review HTTP path and reviewer console UI.
- Config, requirements, docs/ADR, OpenAPI snapshot, backend + frontend tests.

## Out of scope

- Authoritative registrar/barcode verification (documented residual risk).
- Dropping the legacy `enrollment_verifications` tables (kept for history).
- Guidance Staff reassignment (role retained, no COR duty).

## Acceptance criteria

1. Registration creates `PENDING_VERIFICATION` + screening; clean screening → `AWAITING_CONFIRMATION`, otherwise `NEEDS_RESUBMISSION`.
2. Confirmation activates the account, creates the profile, sets `valid_until`, marks screening `PASSED`, and deletes COR bytes.
3. Missing screening tooling fails closed (`SCREENING_UNAVAILABLE`), never auto-activating.
4. Barcode raw payload and raw OCR text are never persisted or logged (SHA-256 digest only).
5. Campus/program must match existing active rows; extracted text never auto-creates reference data.
6. Strict student-number pattern enforced on confirm.
7. Tests + frontend build + OpenAPI snapshot pass; independent read-only review before acceptance.

## Planned verification

- Backend `pytest app/tests` (MySQL cases skip without `COUNSELCONNECT_TEST_DATABASE_URL`).
- Frontend test suite + `npm run build`.
- `python scripts/export_openapi.py --check`.
- Fresh read-only review.

## Actual verification

- Backend: `pytest app/tests` → 67 passed, 119 skipped (MySQL not configured).
- OpenAPI: regenerated; `python scripts/export_openapi.py --check` reports the snapshot matches.
- Frontend: `npm test` → 57 passed, 2 failed. The 2 failures (`calendar permits a weekend date…`, `calendar month navigation…` in `appointments.test.cjs`) are pre-existing, hard-date/clock dependent, unrelated to this change.
- No live MySQL execution of the new migration (test DB not configured). The migration compiles and the test fixture applies it when a test DB is present.
- `git diff --check` not run: the shell in this environment cannot reach the repo's `.git`.

## Independent review follow-up (2026-09-30)

HIGH-risk read-only review found and the following were fixed:

- HIGH: pending Students could not authenticate (no `StudentProfile` before confirmation, and student-number login requires one). Fixed by an ADR-019 bootstrap exception: non-`ACTIVE` Students sign in with their registration email; added unit tests and updated login copy/docs.
- MED: resubmission after the original 7-day window deleted the new COR immediately → resubmit now grants a fresh window and supports renewal (new screening row) after `valid_until`.
- MED: `confirm` did not independently deny expired evidence → added `SCREENING_EXPIRED` check with commit + purge.
- MED: screening intermediate OCR text/raster pages were written to the shared OS temp dir → moved into the private COR store (`cor_storage_root/tmp`).
- MED: registration endpoint was `async` and blocked the event loop on OCR → made it sync (threadpooled).
- MED: stale tests hitting removed `/enrollment-verifications` endpoints → rewritten to the `cor-screenings` gates.
- LOW: `valid_until` now uses calendar months; counselor list includes the applicant `student_number`; login label updated.

Unresolved human decisions: none from the implementation; residual document-spoofability risk (ADR-029) and dropping the legacy `enrollment_verifications` tables remain open.

## Deviations / unresolved human decisions

- Kept `POST /accounts/register/student` (bare, no-COR) instead of removing it, to preserve unrelated coverage; it still creates a `PENDING_VERIFICATION` account.
- Legacy `enrollment_verification` module code + tables retained (dormant, unrouted) to preserve their privacy regression tests and history.
- Pending/expired Students authenticate with their registration email (ADR-019 bootstrap exception recorded in ADR-029).
- Residual spoofability of document-only auto-activation is documented in ADR-029; an authoritative University source is still pending.

## Follow-up feature (2026-09-30): Counselor "Users" directory

**Status:** COMPLETE.
**Objective:** Active Counselors can view a read-only directory of Student accounts with academic profile and latest COR screening result (parity with the prototype admin list).

- Backend: `GET /accounts/students` (COUNSELOR-only, `q` / `account_status` / `screening_status` / `page` / `page_size`); `AccountsRepository.list_students`, `CorScreeningRepository.latest_for_students`, `CorScreeningService.list_students`, `StudentDirectoryItem` schema.
- Frontend: `useUserDirectory` / `useStudentCount`, `CounselorUsersPage` (`#users`), Counselor sidebar "Users" link, dashboard "Total users" card now live.
- Verification: backend `pytest app/tests` → 70 passed, 120 skipped; OpenAPI snapshot regenerated + check passes; frontend `npm test` → 60 passed, 2 failed (same pre-existing calendar date-rot); `npm run build` succeeded.
- Risk: MEDIUM (localized read-only feature); self-review against acceptance criteria completed, no defects found.

## Follow-up feature (2026-09-30): inline account confirmation on the registration form

**Status:** COMPLETE.
**Objective:** Prototype-style flow — after email + password + COR, the confirmation step renders inside the same registration card (no separate sign-in).

- `useRegistration.register` now auto-signs-in with the submitted credentials after a successful registration (`/auth/login`, email bootstrap) and returns `auth` + `canConfirm`.
- `RegisterPage` is a two-phase card (`form` → `confirm` → `done`): on a clean screening it renders the extracted fields inline (shared `ScreeningFields`), confirms via `POST /cor-screenings/confirm`, and reports activation. `NEEDS_RESUBMISSION`/`FAILED` shows the reason with a link to the re-upload step.
- Extracted the editable field set into `features/accounts/ScreeningFields.jsx`, reused by `RegistrationStatusPage`.
- `App`/`LandingPage` pass `onSignedIn` and an `onActivated` (session refresh) so the header updates to ACTIVE after confirmation.
- Verification: frontend `npm test` → 61 passed, 2 failed (same pre-existing calendar date-rot); `npm run build` succeeded. No backend change in this step.
- Risk: MEDIUM (frontend flow); self-review completed. Note: success now depends on `/auth/login` succeeding after registration; if it fails the student falls back to the sign-in path and the message still guides them.

## Fix (2026-09-30): registration modal was invisible

**Root cause:** `frontend/src/index.css` referenced `--card-bg`, `--text-dark`, `--text-muted`, and `--border-color`, but none were defined in `:root`. `.signup-card { background: var(--card-bg) }` therefore computed to transparent, so the register modal had no surface over the dark `.modal-overlay` (the login modal uses the defined `--counseling-subtle-fill`). The same missing tokens also dropped input borders and muted text colors across the landing/auth UI.
**Fix:** defined the four tokens in `:root`. Verification: `npm run build` success; `npm test` → 61 passed, 2 failed (pre-existing calendar date-rot).

## Change (2026-09-30): read-only student number + academic year on confirmation

**Objective:** prevent edits to the fields that must match the COR barcode.
- `ScreeningFields.jsx` (shared by the status page and the inline confirm step) renders **Student number** and **Academic year** read-only with "cannot be changed" hints.
- Defense in depth: `CorScreeningService.confirm` now rejects a confirmed student number that differs from the screened/extracted value with `STUDENT_NUMBER_MISMATCH` (422); the frontend maps it to a friendly message.
- Verification: backend `pytest` → 71 passed, 120 skipped; frontend `npm test` → 61 passed, 2 failed (pre-existing date-rot); `npm run build` success. Docs updated (`REGISTRATION_VERIFICATION.md`).

## Change (2026-09-30): prototype-flow fidelity — read-only verified fields, Reject, barcode checks, validity

**Objective:** close the docx gaps found by the flow comparison.
- **Read-only verified fields:** `ScreeningFields` now renders student number, names, year level, section, academic year, and any mapped campus/program as read-only; only an unmatched campus/program stays selectable. `CorScreeningService._assert_fields_match` rejects an edited verified field with `FIELD_MISMATCH` (defense in depth).
- **Reject action:** `POST /cor-screenings/reject` sets `NEEDS_RESUBMISSION` / `REJECTED_BY_STUDENT`; wired into both the status page and the inline confirm step.
- **Barcode cross-checks:** the payload's academic period is compared to OCR (`barcode_academic_period_match`, mismatch → `MISMATCH`) and decode certainty is recorded (`barcode_decode_confidence`).
- **Enrollment validity:** the COR validity date is extracted (`extracted_valid_until`, new migration `20260930_extracted_validity`) and used for `valid_until` when in the future.
- **AWAITING tightened:** confirmation now requires every required field to be present (no partial extraction), since fields are no longer editable.
- Verification: backend `pytest` → 75 passed, 120 skipped; OpenAPI regenerated + check passes; frontend `npm test` → 62 passed, 2 failed (pre-existing date-rot); `npm run build` success; screening smoke test on the sample COR → `AWAITING_CONFIRMATION`, decode confidence 1.0.
- Deviations kept: unmatched campus/program stay selectable (approved design) rather than forcing resubmission; PDF-only and the 3-role model unchanged. Still open: `FAILED` for unrecoverable technical errors and a visible `PROCESSING` stage.

## QoL updates (2026-09-30)

- **Auto-logout on reject:** a successful reject calls an `onRejected` handler from App (`session.logout()` + redirect to `#login`); wired into the status page, the inline confirm step, and the landing modal.
- **Visual error notifications:** new `components/feedback/Notifications.jsx` (`ToastProvider`/`useToast`, accessible toast host, dismissible, variants). `apiClient` now exposes `setErrorHandler` and reports every failed request and network failure; App raises a toast for API errors, session errors, and an unreachable API.
- **Counselor complete profile:** `CounselorUsersPage` rows now open a detail modal showing account, full academic profile, and the complete screening record (status, scores, barcode, extracted fields, validity, timestamps).
- **Contrast fixes:** darker `--text-muted` (#4b5563) and `--border-color` (#d1d5db), card borders, a global `:focus-visible` outline (WCAG 2.4.7), stronger badge/muted-text colors, and higher-contrast read-only fields and status text.
- Verification: frontend `npm test` → 66 passed, 2 failed (pre-existing calendar date-rot); `npm run build` success; no backend change.

## Process-flow gaps #7/#8/#9/#11 (2026-09-30)

- **#7 Email-or-student-number login:** `AuthService._find_user_by_identifier` now returns a Student matched by registered email regardless of status; staff (incl. Superadmin) still use email and take precedence over a colliding student number.
- **#8 `FAILED` for technical failures:** `derive_outcome` returns `FAILED` / `TECHNICAL_ERROR` for decoder/processing failures that cannot be attributed to the document; unreadable/low-confidence/barcode-inconsistency stay `NEEDS_RESUBMISSION`.
- **#9 Visible `PROCESSING`:** registration and resubmission persist the screening as `PROCESSING` (committed) before resolving it in a second commit.
- **#11 `SUPERADMIN` role:** migration `20260930_superadmin_role` widens `chk_users_role`; model/schema/auth updated; the role signs in with email, reads the student directory (`GET /accounts/students`), and can recover a non-active Student (`POST /accounts/students/{user_id}/recover` → `PENDING_VERIFICATION`, open screening `NEEDS_RESUBMISSION`/`ADMIN_RECOVERY`, audit `account_recovery`). It cannot approve CORs. Frontend: Superadmin sidebar/routes + a Recover action on the Users page.
- Verification: backend `pytest` → 80 passed, 39 skipped (unit/api; MySQL cases skip); OpenAPI regenerated + `--check` passes; frontend `npm test` → 67 passed, 2 failed (pre-existing date-rot); `npm run build` success; migrations applied to the dev DB (`20260930_superadmin_role` head).
- Docs: ADR-003/019 amended, ADR-030 added; `USER_ROLES.md`, `API_CONTRACT.md`, `REGISTRATION_VERIFICATION.md` updated.

## Dev superadmin seed (2026-09-30)

- `backend/dev_seed.sql` now seeds `superadmin@ucc.edu.ph` / `superadmin-dev-2026` (Argon2id, `SUPERADMIN`, `ACTIVE`) alongside the counselor.
- Applied to the local dev DB (user_id 12); login verified via `AuthService.login`.
- `docs/TEAM_SETUP_GUIDE.md` demo flow/quick reference updated for the automated flow, the Users directory, and both seeded staff accounts (the stale reviewer-console steps were removed).
- Dev-only credentials; rotate before any real deployment.

## Docs sweep (2026-09-30)

Updated stale role/flow references for ADR-029/030:
- `AGENTS.md` — roles now include `SUPERADMIN`; Guidance Staff has no COR duty; COR deleted after confirmation/resubmission or TTL.
- `README.md` — four-role paragraph; pending-decisions section points to ADR-019–027 and lists the remaining COR limits.
- `docs/WORKFLOWS.md` — account lifecycle now automated screening → confirm/reject → ACTIVE; email-or-number login.
- `.ai/NAMING_CONVENTIONS.md` — examples/tables/states/audit events moved from `enrollment-verification` to `cor_screening`; added `SUPERADMIN` to the Role row; legacy verification row labelled.
- `docs/SYSTEM_OVERVIEW.md` — Superadmin mentioned.
- Left unchanged intentionally: `design/DFD_AI_Readable_FULL.md` (large generated design artifact showing the original Staff COR-review flow), and historical changelog/plan files (`.kilo/plans/*`, `frontend/docs/UI_CHANGES.md`).

