# CounselConnect - Current Task

**Status:** ACTIVE
**Task:** Merge `CounselConnect-test-Registration_Fix/` (registration QoL, auth CSRF/audience gate, appointment scheduling) into the calls work per `.kilo/plans/1792774405483-video-demo-test-button.md`.
**Route:** `appointments` + `auth` + `registration` + `security`; HIGH risk (auth/session behavior, migration, scheduling authorization).

## Objective

Land every non-local snapshot change on top of the appointment-call feature without regressing calls or deleting current docs. The nested `CounselConnect-test-Registration_Fix/` folder stays as an untracked, read-only historical reference.

## Scope

- In: auth CSRF null-on-anonymous, login audience gate, registration UI (`CorUpload`, `PasswordInput`, `RegisterPage`), appointment backend (booking counselors, scoped calendar/slots, weekday schedules, enable/delete, `is_deleted` migration), appointment frontend (month calendar, booking modal, counselor management), CSS, tests, and merges of B's doc wording.
- Out: snapshot's `.ai/`, `contracts/openapi.json`, `docs/AUDIO_VIDEO_CALLS.md`, its deletions of `TEAM_SETUP_GUIDE.md`/`WORKFLOWS.md`, and its local artifacts (`.venv`, `node_modules`, `dist`, `var`, patch/image files).

## Acceptance Criteria

- Calls module, `AppointmentCallPanel`, `services/realtime.js`, `test_calls.py`, and `appointment-call.test.cjs` survive the merge unchanged in behavior.
- `GET /auth/csrf` returns `200 null` when anonymous; `useSession.restore` stays signed out instead of throwing.
- Student and staff login forms reject the other audience and revoke the fresh session.
- `alembic heads` is `20261024_weekly_sched_softdel`; migration upgrade adds `is_deleted`, downgrade removes it, existing rows are preserved.
- `contracts/openapi.json` regenerated from the merged app and matches.
- `docs/` keeps `AUDIO_VIDEO_CALLS.md`, `TEAM_SETUP_GUIDE.md`, `WORKFLOWS.md` while gaining B's wording.

## Verification Planned

- Backend targeted (`test_appointments`, `test_calls`, `test_auth_flow`, `test_calendar`, `test_recurring_schedules`) then full suite with the disposable MySQL test DB.
- `scripts/export_openapi.py --check`, migration round-trip test, `alembic` head check.
- Frontend targeted then `npm test`, `npm run build`.
- `git diff --check` and explicit `git status`.
- Fresh read-only HIGH-risk review before acceptance.

## Human Decisions Still Needed

- None blocking. Manual two-browser call and device QA remain human checks.

## Progress

1. Calls work checkpointed on `merge/calls-checkpoint` (`e3d5bc1`).
2. Snapshot delta applied on `merge/snapshot-fix` (`de76c4d`) from `f9abe19`; 39 files.
3. Merge `940c9c3` resolved one import conflict in `appointments/service.py`.
4. Post-merge fixes: test-harness migration loader, doc decoding repair, calendar/booked-slot test fixes.

## Verification Results

### Passed

- Backend targeted: `test_appointments` 65 passed; `test_calls` + `test_auth_flow` passed in the combined run (118 passed before the post-merge fixes); `test_calendar` 5 passed; `test_recurring_schedules` 9 passed.
- Full backend suite: **261 passed, 1 failed** — only the pre-existing `test_live_appointment_screens` harness failure (`StudentHomePage` `useToast` outside `ToastProvider`), unchanged from before this merge.
- `scripts/export_openapi.py --check`: matches the application.
- `alembic heads`: `20261024_weekly_sched_softdel` (single head).
- Frontend `npm test`: **94 passed, 0 failed** (B's dynamic-date calendar tests replaced the two date-rot failures).
- `npm run build`: succeeded (81 modules).
- `git diff --check`: no whitespace errors (line-ending warnings only).

### Remaining limitations

- Interactive two-browser call, real camera/TURN behavior, and Capacitor remain human checks.
- `CounselorAppointmentsPage` now defaults its status filter to `PENDING` (user-visible change from the snapshot).
- The snapshot's legacy `.ai/` and `docs/AUDIO_VIDEO_CALLS.md` were deliberately not applied.
