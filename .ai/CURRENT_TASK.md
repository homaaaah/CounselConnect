# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** Merge `CounselConnect-test-Registration_Fix/` (registration QoL, auth CSRF/audience gate, appointment scheduling) into the appointment-call work per `.kilo/plans/1792774405483-video-demo-test-button.md`.
**Route:** `appointments` + `auth` + `registration` + `security`; HIGH risk (auth/session behavior, migration, scheduling authorization).

## Result

The snapshot's product changes now sit on top of the appointment-call feature on branch `merge/calls-checkpoint`. Students get the six-stage counselor-first booking flow and a month calendar; Counselors get scoped calendar/booked-slot views, standard weekday availability, enable/disable/soft-delete, and a working self-scoped reschedule. Anonymous startup probes no longer surface a 401, and the Student/staff login forms reject and revoke the wrong audience. `counselor_weekly_schedules.is_deleted` exists with a soft-delete path that keeps existing slots and appointments valid while removing the definition from listings and future availability. Calls, the call panel, `services/realtime.js`, `test_calls.py`, and `appointment-call.test.cjs` were preserved. `CounselConnect-test-Registration_Fix/` stays an untracked, read-only historical reference.

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
