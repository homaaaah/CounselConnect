# Current work: Registration Corrections and Users Management

## Separate Superadmin sign-in (2026-10-26)

Follow-up: removed Student and Guidance sign-in switches from both Superadmin page and modal, as requested. Preserved credentials, submission, audience checks, modal close and standalone landing navigation. Removed the unused Guidance-switch callback. Focused session tests passed (18); production build passed (90 modules).

**Status: COMPLETED.** User requested a separate Superadmin sign-in section with focused verification only. Added a dedicated `#superadmin-login` entry, green-accented Superadmin form and landing-footer/login-modal switches using the existing LoginPage, session API and CSRF controls. Superadmin form accepts only SUPERADMIN; Guidance form accepts COUNSELOR/GUIDANCE_STAFF. Wrong-audience sessions use the existing logout flow. Protected Superadmin page fallbacks now show the matching form, and that form has no public registration prompt. Student/Guidance sign-in, registration, role-bound resource authorization and sign-out are preserved. No backend/schema/account changes.

Verification: 18 focused session/audience tests and 10 navbar regressions passed (28 distinct checks), including separate route/modal access, valid Superadmin acceptance, rejected other roles, Guidance rejection of Superadmin, logout/CSRF and landing-modal switching. One new test selector was scoped to the dialog to exclude the landing hero heading. Production build passed, 90 modules, with the existing approved esbuild sandbox exception. Browser management harness uses the dedicated Superadmin route; full backend/browser suites were intentionally not rerun per user request. Diff/whitespace and Node syntax checks passed. Role/audience separation is a frontend entry convention; unchanged backend role/session checks remain authoritative.

---

## Counselor account creation and editing (2026-10-26)

**Status: COMPLETED.** User authorized Superadmin creation/editing of Counselor accounts and selected a Superadmin-entered initial password. This supersedes prior developer-only Counselor provisioning/no-provisioning scope, narrowly for Counselor accounts (ADR-035). Route: accounts API + auth-rbac + existing Users UI; HIGH risk. No schema migration was required.

Scope: strict names/email/initial-password creation with server-fixed COUNSELOR/ACTIVE/enabled state; names/email editing of exact Counselor IDs with displayed updated_at conflict checks; email edits atomically revoke sessions, preserve password/status/clinical/appointment state and recheck login identity under the existing User lock. No role reassignment, password-reset/email-delivery mechanism, Student/staff profile editing or clinical access. Initial passwords remain request/form-only and hash through existing Argon2id; safe audit metadata contains field names/outcomes only.

Contracts to preserve: all existing paged Users/review/recovery/navigation behavior; CSRF/session/fresh active Superadmin enforcement; protected non-Counselor targets; original Counselor IDs and relationships; no secret values in responses/audits/errors. Verify with disposable-MySQL role/input/privacy/rollback/concurrency/login tests, frontend API-boundary create/edit tests, isolated browser flows and build. Complete a separate read-only security review of the final diff before acceptance. No real accounts will be created or edited during testing.

**Implemented:** `POST /accounts/users` and `PATCH /accounts/users/{user_id}` use strict Counselor request DTOs and existing safe/no-store managed-user responses. Creation fixes role/status/enabled state and hashes the Superadmin-entered password; editing only allows names/email plus the displayed timezone-aware `expected_updated_at`. Duplicate email/Student-number shadow checks, fresh actor/target locks, monotonic stale-edit protection, atomic safe audit/session revocation and login identity recheck are implemented. Users provides Create Counselor and Counselor-only Edit forms with password confirmation, retained error input and close protection while saving. No password reset/delivery or role/status editing was added. Owning role/security/requirements/decision docs and generated OpenAPI were updated.

**Checks run:** 85 combined focused backend tests passed (new account API cases plus auth/Users regressions); 4 real independent-connection race tests passed (both login/email-edit orders, two stale edits, duplicate creation); strict-timestamp rerun passed 6, including one added numeric-timestamp rejection. This is 90 distinct backend tests across scoped runs, not a full backend suite. Full frontend suite: 134 passed; the 5 new form workflow tests passed again after the password label accessibility fix. Desktop/mobile-sized Chrome create/edit workflows: 2 passed against real FastAPI/disposable MySQL, including initial login, email rename, old-session denial, old-email rejection and new-email login. Production build passed (90 modules) with the known approved esbuild sandbox exception. OpenAPI matches; Python/Node parsing and tracked/new-file whitespace checks pass. Existing TestClient deprecation warnings remain.

**Security review:** A fresh read-only in-task review checked actor/target authorization, strict input and timestamp handling, fixed role/state on creation, secret-free projections/audits/errors, duplicate/rollback behavior, lock ordering, stale-form identity and both login race orders. No additional production fix was required by that review. Tests use owned disposable schemas/accounts; no application account, schema or service was changed. Physical devices remain untested; browser mobile checks use a desktop Chrome viewport. No commit or staging action was performed.

---

## Superadmin UI polish (2026-10-26)

**Status: COMPLETED.** Objective: consistent, responsive layout across Users, Registration Corrections, recovery directory, details, confirmations and navigation. Route: `ui-refactor` + owning registration contract. Scope is presentation and accessible dialog behavior; no backend, schema, account, permission or workflow changes. Existing application data was not used for browser tests.

### Contracts to preserve

| Invariant / capability | Source | Verification |
|---|---|---|
| Selected User/request ID and displayed version including legacy null reach the exact action | Users/Corrections pages, management hooks, API client | management workflow and real browser/API tests |
| Server pages, filters, totals, stale-response guards and unknown legacy values survive | existing hooks and registration contract | management workflow tests |
| Recovery/details and protected-role behavior remain; Counselor directory remains read-only | CounselorUsersPage and accounts contract | user-directory tests and browser checks |
| Preview remains temporary and revoked on close/navigation/expiry/decision | PrivateCorPreview | workflow and browser checks |
| Same role-scoped routes, sign-out, Student and Counselor navigation | AppNavBar/App | navbar, directory and full frontend tests |

Acceptance: shared visual treatment on all Superadmin surfaces, usable mobile tables/forms/dialogs, keyboard/Escape/focus handling, existing workflow assertions passing and production build passing. Verify through isolated browser/API/MySQL, never the application database. Intentional changes: consistent presentation and direct navigation to the existing recovery route; all API paths/payloads/permissions remain compatible. No unresolved product decisions.

**Result:** Added shared Superadmin page/panel/dialog/badge/detail components and scoped green/neutral styling. Users, Corrections and Account Recovery now share page hierarchy, visible filter labels, consistent controls, table spacing, pagination, status badges, detail groups and confirmation areas. Dedicated responsive dialogs replace registration-card reuse; body scrolling is locked, keyboard focus is contained/restored, Escape and accessible inline close icons work. Correction comparison highlights recorded changed fields while preserving unknown legacy context. Recovery dates now use the same Asia/Manila display as Users/review, and its existing fields/actions remain. Navigation links directly to recovery, marks Users active on the shared home route and collapses earlier to avoid crowded tablet navigation. Counselor/Student presentation and backend authority remain intact.

**Verification:** Latest full frontend suite 129 passed; production build passed, 89 modules. Combined disposable-MySQL integration selection passed 8 cases (6 real desktop/mobile-sized Chrome workflows including stale decisions/session revocation, plus 2 renderer/API flows). Browser checks were extended for recovery search/details, modal focus/body lock/Escape/focus restoration, viewport fit and preview navigation cleanup. Visual review found an off-screen table label widening the mobile recovery page; positioning its scroll container contains that label. The final isolated REGISTRATION/mobile workflow passed again after all presentation fixes, including the explicit page-width assertion. Synthetic screenshots were inspected. Separate diagnostic sandbox retries encountered loopback transport and pytest-temp permission failures; final mobile verification used approved escalation and a fresh workspace-owned temporary directory. Vite's harness now reserves an ephemeral port rather than competing with the user's 5173 server. Existing TestClient deprecation warnings remain.

**Review/limits:** Read-only in-task review confirmed unchanged methods/payloads, clicked IDs/versions, pagination, stale-response guards, legacy unknowns, private preview lifecycle, protected-role and recovery rules. No application database/service was changed for this UI task. Physical-device/native-PDF/OCR limits from the release record remain; desktop browser viewport tests do not establish them. No commit or staging action was performed.

---

**Status: Implementation, milestones 1-4, rehearsal and authorized local application migration complete (2026-10-26).** No feature implementation is knowingly outstanding. The user authorized stopping the local backend and applying the three migrations, reserving functional testing for themselves. Backend remains stopped. No staging/production deployment or commit was performed.

**Local login repair (2026-10-26):** Diagnosed the shared login 500 as code/schema mismatch: application DB was at `20261024_weekly_sched_softdel` without `users.is_deactivated` or other release columns. On explicit user authorization, stopped the Uvicorn supervisor and spawned worker, confirmed port 8000 closed, created a Windows-current-user DPAPI-encrypted SQL backup and verified its isolated restore against all table row counts. Rechecked duplicate pending owners with backend stopped: zero. Applied the three existing Alembic migrations to `20261025_pending_correction`. Verified release columns, generated unique guard, preserved table/status counts, false deactivation/REGISTRATION defaults and unknown legacy context. Backend was not restarted and login/functional testing was not performed, per the user's instruction.

**Backup:** Ignored `backend/var/backups/pre_registration_release_20261026T011840Z.sql.dpapi` with adjacent manifest; encrypted for the current Windows user. No plaintext SQL dump or private COR bytes were persisted. Temporary restore schema and helper script were removed. Retain this recovery backup outside the commit until the user completes testing and the recovery window closes.

**Local development account (2026-10-26):** User's subsequent Superadmin login returned 401 because no SUPERADMIN account existed in the local application database. Added only the documented `superadmin@ucc.edu.ph` development seed account, ACTIVE/non-deactivated, with Argon2id credentials matching `backend/dev_seed.sql`. No existing account was overwritten and no HTTP login test was performed; user will test through Guidance sign in. The earlier pre-migration backup predates this seed insertion.

## Contracts and release references

- Owning behavior/privacy contract: [REGISTRATION_CORRECTIONS.md](../docs/REGISTRATION_CORRECTIONS.md).
- Final verification and remaining checks: [REGISTRATION_CORRECTIONS_HANDOFF.md](../docs/REGISTRATION_CORRECTIONS_HANDOFF.md).
- Pinned migration, backup, rollback and smoke-check plan: [REGISTRATION_CORRECTIONS_DEPLOYMENT.md](../docs/REGISTRATION_CORRECTIONS_DEPLOYMENT.md).
- Preserve registered baselines separately from proposals, immutable version lineage, exact selected IDs/displayed versions (including legacy null), complete pagination and unknown legacy values.
- Review permissions remain Superadmin-only; Student reads/revisions are owner-scoped. Users status actions target only Students/Counselors, revoke sessions atomically and preserve enrollment restrictions. Backend authorization is authoritative.
- Exact COR evidence stays private and temporary, bounded by decision/replacement or original seven-day upload deadline. Preview blob URLs are revoked on close/navigation/expiry/decision. No clinical authority or data is added.
- Mobile menu fix preserves role-scoped links/hash routes/open-close/aria-expanded behavior. Inline SVG and a fixed touch target remove the external icon-font dependency; no API or permission changes.

## Verification retained

| Check | Result |
|---|---|
| Combined relevant backend/security/migration selection | Initial 946 passed, 10 failed; affected rerun 259 passed with only the appointment harness still failing; repaired appointment flow passed separately. All 956 distinct selected tests have passing results across runs, not a single clean 956-test or full-backend-suite result. |
| Frontend integration milestone | 129 tests passed, including 13 management cases; two real React/API/disposable-MySQL management workflows passed. |
| Actual Alembic runner rehearsal | 1 passed: disposable pre-release schema upgraded through all three release migrations, row/default/legacy preservation, pending unique guard and no-op retry verified. |
| Real Chrome browser rehearsal | 4 desktop/mobile-sized core cases and 2 stale-decision/session-revocation follow-ups passed across both proof purposes. Uses real Vite/FastAPI/disposable MySQL, synthetic data, stubbed extraction and blocked external resources. |
| Checks after mobile menu/shared harness changes | 10 navbar tests and 2 existing renderer/API workflows passed. |
| Production build | Latest build passed, 87 modules; approved escalation resolved the existing esbuild ancestor-directory sandbox read restriction. |
| Consistency | OpenAPI matches; single Alembic head `20261025_pending_correction`; changed/new Python and Node harness parsing and whitespace checks passed. Graphify inactive. |

Existing TestClient and Alembic path-separator deprecation warnings remain. Test suites and reusable harnesses are release assets; retain them.

## Remaining manual/deployment work

Native PDF reader visual rendering, actual mobile/Capacitor, genuine approved synthetic COR through PDF/barcode/OCR tools and camera/TURN/device behavior remain unverified. PDF response/frame/blob checks and mobile-sized desktop Chrome do not establish native-reader or physical-device behavior.

The local application migration and protected backup/isolated restore are now complete. User will restart the backend and perform functional testing. Future migrations/other targets still require their own confirmed target, protected backup/restore, stopped writers and the pinned upgrade/guarded recovery procedure. Never load clean-install SQL into an existing database or force a lossy downgrade.

## Pre-commit cleanup

Removed the three generated synthetic rehearsal screenshots from ignored `backend/var/rehearsal/` and condensed duplicated incremental progress/obsolete resume instructions in this file and the handoff. Preserved implementation, migrations, tests, dependencies, build output, environment files, private stores and unrelated work. No commit or staging action was performed. Do not resume historical implementation increments or repeat unchanged coverage solely because documentation was condensed.

---

The following is the previous completed task record, retained for context.

# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** Merge `CounselConnect-test-Registration_Fix/` (registration QoL, auth CSRF/audience gate, appointment scheduling) into the appointment-call work per `.kilo/plans/1792774405483-video-demo-test-button.md`.
**Route:** `appointments` + `auth` + `registration` + `security`; HIGH risk (auth/session behavior, migration, scheduling authorization).

## Result

The snapshot's product changes now sit on top of the appointment-call feature on branch `merge/calls-checkpoint`. Students get the six-stage counselor-first booking flow and a month calendar; Counselors get scoped calendar/booked-slot views, standard weekday availability, enable/disable/soft-delete, and a working self-scoped reschedule. Anonymous startup probes no longer surface a 401, and the Student/staff login forms reject and revoke the wrong audience. `counselor_weekly_schedules.is_deleted` exists with a soft-delete path that keeps existing slots and appointments valid while removing the definition from listings and future availability. Calls, the call panel, `services/realtime.js`, `test_calls.py`, and `appointment-call.test.cjs` were preserved. The `CounselConnect-test-Registration_Fix/` reference folder was merged and then removed; its delta remains in `merge/snapshot-fix` (`de76c4d`).

## Branch / commits

- `merge/calls-checkpoint` — `e3d5bc1` calls checkpoint, `940c9c3` merge of `merge/snapshot-fix` (= `de76c4d`, applied on `f9abe19`), `cac4186` post-merge harness/docs fixes, `8e23d8a` review fixes, `d0d2e3b` hardening. No push.

## Merge decisions

- Copied an explicit allow-list from the snapshot; never a whole-tree copy.
- Excluded the snapshot's `.ai/`, `contracts/openapi.json`, `docs/AUDIO_VIDEO_CALLS.md`, its deletions of `TEAM_SETUP_GUIDE.md`/`WORKFLOWS.md`, and all local artifacts.
- Regenerated `contracts/openapi.json` from the merged app instead of merging JSON.
- Repaired double-encoded (cp1252/UTF-8) text in the copied `docs/API_CONTRACT.md` and `docs/APPOINTMENT_SCHEDULING.md`.
- Dropped the unreferenced `frontend/src/assets/bg.jpg`, matching the snapshot.

## Fixes found by review (not present in the snapshot)

- `backend/app/tests/conftest.py`: added the missing `20261024_weekly_sched_softdel` loader/call.
- `appointments/service.py`: `appointment_response` normalizes slot datetimes with `db_time` (aware/naive comparison crash).
- `appointments/service.py`: imported `WeeklyScheduleCreateRequest`; the standard-weekday action previously raised `NameError`.
- `appointments/{service,repository}.py`: booking/reschedule now reject slots generated from a disabled or soft-deleted weekly schedule (`slot_schedule_is_active`, locking current read).
- `BookingModal.jsx`: Counselors start at the calendar step (`selfCounselorId`), cannot go back to the empty directory step, and candidates are filtered to `AVAILABLE`.
- `CounselorAppointmentsPage.jsx`: standard-weekday button is gated on a duration that divides the 8-hour block, not on the unrelated custom range.
- `useCounselorDashboard.js`: restored paging so "today" is not truncated at 100 records.
- `docs/COUNSELOR_FIRST_BOOKING_PLAN.md`: acceptance criteria now match the shipped unpaginated `GET /booking-counselors`.
- Tests added: calendar `booked_slots` counselor-only, stale-schedule booking rejection, standard-weekday all-or-nothing batch, enable/soft-delete round trip, migration round trip, Counselor reschedule, isolated Origin rejection.

## Verification (all run)

- Backend targeted: `test_appointments` 68 passed, `test_calls` 23 passed, `test_calendar` 5 passed, `test_recurring_schedules` 9 passed, `test_auth_flow` passed.
- Full backend suite with the disposable MySQL test DB: **265 passed, 1 failed** — only the pre-existing `test_live_appointment_screens` harness failure (`StudentHomePage` `useToast` outside `ToastProvider` in `frontend/tests/live-appointments.cjs`), unchanged from before this merge.
- `python scripts/export_openapi.py --check`: matches the application.
- Alembic: single head `20261024_weekly_sched_softdel`; migration upgrade adds `is_deleted`, downgrade removes it, rows preserved (covered by a scratch-schema test).
- Frontend `npm test`: **95 passed, 0 failed** (the snapshot's dynamic-date tests also cleared the two pre-existing calendar date-rot failures).
- `npm run build`: succeeded (81 modules).
- `git diff --check`: no whitespace errors (line-ending warnings only).
- Two read-only HIGH-risk reviews. Confirmed findings fixed: Counselor reschedule dead end, stale-slot booking, missing standard-weekday import, lock inconsistency, preselected RESERVED counselor candidate, duration-45/90 weekday 422, dashboard truncation, and the Origin test's lack of isolation.

## Not run

- Interactive two-browser call, real camera/TURN behavior, and Capacitor. These need devices/browsers and remain human verification.
- Manual QA checklist from the plan (audience mismatch, anonymous CSRF, registration upload/password UX, counselor selection, calendar month/booked slots, weekday/enable/delete, toasts, live call).

## Remaining limitations

- `CounselorAppointmentsPage` now defaults its status filter to `PENDING` (snapshot behavior change; intentional).
- `docs/TEAM_SETUP_GUIDE.md` and `docs/WORKFLOWS.md` are kept even though the snapshot deleted them.
- The temp worktree `C:\Users\delac\AppData\Local\Temp\kilo\cc-snapshot-fix` and branch `merge/snapshot-fix` are still registered for review.
- TURN uses static environment credentials; one backend process only (in-memory room registry); both call participants must join explicitly.
