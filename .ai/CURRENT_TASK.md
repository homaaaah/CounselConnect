# Current work: Registration Corrections and Users Management

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
