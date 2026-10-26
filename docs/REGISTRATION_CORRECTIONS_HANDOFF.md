# Registration Corrections and Users Management: completion handoff

Updated 2026-10-26 after implementation, local rehearsal, pre-commit cleanup and authorized local application migration. This is the final progress record; [REGISTRATION_CORRECTIONS.md](REGISTRATION_CORRECTIONS.md) remains the owning contract.

## Completion and remaining scope

**Milestones 1-4, local rehearsal and authorized local application migration are complete.** No feature implementation is knowingly outstanding. The user subsequently authorized stopping the backend and applying all three migrations, reserving functional testing for themselves. Backend remains stopped. No staging/production deployment or commit was performed.

**Latest local login repair (2026-10-26):** Shared login 500 was traced to the application DB at `20261024_weekly_sched_softdel`, missing `users.is_deactivated` and other release columns. Stopped the Uvicorn supervisor/spawned worker and confirmed port 8000 closed. Created a Windows-current-user DPAPI-encrypted SQL backup, verified decryption and isolated restore/all table counts, and removed the temporary restore schema. Stopped-backend duplicate-pending count: zero. Applied all three Alembic migrations to `20261025_pending_correction`; verified exact head, release columns/unique guard, preserved table/status counts, default flags/purpose and unknown legacy context. No login/functional tests or restart were performed, per user instruction.

Recovery backup: ignored `backend/var/backups/pre_registration_release_20261026T011840Z.sql.dpapi` and adjacent manifest. No plaintext SQL or private COR bytes were persisted. Backup requires the same Windows user's DPAPI keys; retain it outside the commit through user testing/recovery. Temporary helper script was removed.

**Local development Superadmin (2026-10-26):** Subsequent 401 was caused by the documented seed account being absent (zero SUPERADMIN accounts). Added only `superadmin@ucc.edu.ph` with the existing `backend/dev_seed.sql` development credentials, ACTIVE/non-deactivated, using Argon2id. Stored hash/flags verified; no existing account changed or HTTP login test performed. User will test Guidance sign in. The recovery backup above predates this seed insertion.

Remaining checks: user restart and functional testing of the migrated local application, native PDF visual rendering (including actual mobile open/close), physical mobile/Capacitor, an approved synthetic COR through installed PDF/barcode/OCR tools and camera/TURN. Browser response/frame/blob checks and desktop mobile-sized viewports do not establish device/native-reader behavior. Local application preflight and backup/restore are now verified.

For a future authorized application deployment, use [REGISTRATION_CORRECTIONS_DEPLOYMENT.md](REGISTRATION_CORRECTIONS_DEPLOYMENT.md). Identify the exact target/service, verify protected backup and isolated restore, stop all writers and run aggregate duplicate-pending preflight before the pinned upgrade. Never load clean-install SQL into an existing database, invent legacy snapshots or clear business data to force rollback.

## Completed release

| Area | Final result |
|---|---|
| Correction backend | Five-field canonical validation; immutable extraction/registered snapshots; stable ownership/version lineage; one-pending database guard; owner-scoped Student reads/history; exact private evidence and bounded retention; version-bound whole-request approval/return; fresh-COR revisions; registration/correction purpose isolation. |
| Users/security | Safe SQL-paged all-role search/filter/detail; protected Student/Counselor deactivate/reactivate; atomic audit/session revocation; login/status races; token/recovery and HTTP/socket enforcement; enrollment/clinical state preserved. |
| Frontend | Superadmin Users and correction review; full filters/pagination; selected IDs/displayed versions including legacy null; current/baseline/proposal comparisons; unknown legacy context; safe stale-response/conflict handling; full history; temporary preview cleanup; Student outcomes/fresh-COR revision; existing recovery/enrollment/clinical navigation. |
| Final fixes | Reviewer comparisons skip Student-only capability queries; pending-duplicate migration refusal typo corrected; stale auth/CSRF/purpose/pagination test assumptions repaired; appointment renderer harness aligned with current controls; mobile menu uses inline SVG/fixed touch target when external fonts fail. |

## Verification evidence

| Check | Actual result and limits |
|---|---|
| Relevant backend/security/migration run | 48 files, 956 selected tests: initial 946 passed/10 failed; affected 12-file rerun 259 passed/1 appointment-harness failure; repaired appointment flow passed separately. Strengthened Users pagination case also passed separately. All 956 distinct tests have passing results across runs; no single clean 956-test or full-backend-suite claim. |
| Frontend milestone | 129 tests passed, including 13 management cases; two real React/API/disposable-MySQL management flows passed. |
| Real Alembic runner | 1 rehearsal passed: owned pre-release schema upgraded through all three release migrations, reached pinned head, preserved rows/defaults/legacy unknowns, verified pending unique guard and no-op retry. |
| Real Chrome core workflows | 4 passed: 1440x1000 desktop and 390x844 mobile-sized viewports across REGISTRATION/CORRECTION proof purposes. Real App/Vite navigation, Users paging/search/detail, selected-account confirmations, preview close/navigation/decision cleanup, return/revision/approval. Synthetic mobile screenshots inspected. |
| Browser follow-ups | 2 passed across both proof purposes: stale second-tab decision gets 409 and refreshes; prior Student session denied after deactivation and reactivation; fresh login shows approved outcome. A valid locally generated one-page PDF was supplied; native PDF rendering remains unverified. |
| Latest affected regressions | 2 renderer/API management workflows and 10 navbar tests passed after shared harness/mobile menu changes. |
| Production build | Latest build passed, 87 modules; approved escalation resolved the known esbuild ancestor-directory sandbox read restriction. |
| Consistency | OpenAPI matches; one Alembic head `20261025_pending_correction`; changed/new Python/Node parsing and tracked/untracked whitespace checks passed. Graphify inactive. |

Existing TestClient and Alembic path-separator deprecation warnings remain. Browser rehearsal uses installed Playwright/Chrome, loopback Vite/FastAPI, disposable MySQL, synthetic accounts/private files, stubbed extraction and blocked external font/icon requests. Servers/browser and owned rows/schemas are cleaned by the harness. It does not verify real OCR, physical devices or native PDF reader rendering.

## Migration and implementation map

Release chain after `20261024_weekly_sched_softdel`:

1. `20261025_correction_context`: nullable immutable snapshots, evidence/version/lineage context and RETURNED support; historical context stays unknown. Downgrade refuses populated context/returned decisions.
2. `20261025_account_screening_scope`: independent `users.is_deactivated` and screening `purpose` with defaults/checks. Downgrade refuses nondefault business state.
3. `20261025_pending_correction`: generated pending-owner ID and unique `uq_profile_change_requests_pending_student`. Preflight refuses duplicate pending owners without choosing/changing requests; retry and downgrade preserve business rows.

MySQL DDL commits independently. Stop writers for migration/recovery, inspect partial failures and follow the deployment plan; never manually patch deployed schema or resurrect expired evidence.

- Backend: `backend/app/modules/{profile_change,cor_screening,accounts,auth}/`, shared authorization/private responses and existing calls/messaging socket revalidation.
- Frontend: `frontend/src/pages/superadmin/{UsersManagementPage,CorrectionsPage}.jsx`, `features/accounts/{management,StudentCorrections}.jsx`, `RegistrationStatusPage.jsx`, `App.jsx`, `AppNavBar.jsx`, `services/apiClient.js`.
- Routes: Superadmin `#users`/`#home`, `#corrections`, separate recovery `#student-directory`; active Student retains `#registration`.
- Tests: correction/Users/auth/socket/migration suites; `test_management_frontend.py` with `live-management.cjs`; opt-in `test_management_browser.py` with `browser-management.cjs`; `test_registration_release_rehearsal.py`. Exact rehearsal commands are in the deployment plan.

## Pre-commit state

Implementation, all three migrations, contracts, reusable test suites/harnesses and the deployment plan must be committed together. Preserve modified/untracked release files and unrelated work; untracked source files are not disposable.

Pre-commit cleanup removed the three generated screenshots from ignored `backend/var/rehearsal/` and condensed duplicated historical progress and obsolete continuation gates here and in `.ai/CURRENT_TASK.md`. Dependencies, existing private stores/environment files and reusable build output were retained. No staging or commit was performed.

Do not resume completed historical increments or repeat unchanged test/build coverage solely because this record was condensed. The remaining work is the explicit manual/deployment scope above.
