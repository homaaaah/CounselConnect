# Merge `CounselConnect-test-Registration_Fix/` into the top-level repo

**Status:** READY FOR IMPLEMENTATION
**Risk:** HIGH (auth/session behavior, registration UX, appointment scheduling, new migration)
**Base:** current `main` = `f9abe19`; the video-call work is uncommitted on top of it.
**Source:** `CounselConnect-test-Registration_Fix/` — a tracked, nested full snapshot of the same base with uncommitted registration + appointment changes. It is **not** a separate Git repository and it does **not** contain the video-call work.

## Goal

Bring the snapshot's product changes into the top-level project while preserving the
appointment-call feature and the current green design. Keep the nested folder as a read-only
historical reference.

## Decisions

1. **Scope:** port **all** non-local snapshot changes: registration/auth QoL, appointment scheduling
   and notifications, CSS/components, the `is_deleted` weekly-schedule migration, and their tests.
2. **Mechanics:** checkpoint the video-call work, build a `merge/snapshot-fix` branch from
   `f9abe19`, apply the snapshot delta there, then 3-way merge it into the checkpoint. No push.
3. **Reference folder:** keep `CounselConnect-test-Registration_Fix/` untouched; exclude it from the
   delta, builds, tests, and imports. Add a short note that it is historical.
4. **Docs:** do not copy the snapshot's docs wholesale. Merge its wording into current docs; keep
   `AUDIO_VIDEO_CALLS` (implemented calls), `TEAM_SETUP_GUIDE`, and `WORKFLOWS`.
5. **OpenAPI:** regenerate after the merge; never copy the snapshot's `contracts/openapi.json`.
6. **Source truth:** apply what the snapshot's **code** contains. Do not additionally implement the
   source's `registration-ui-qol.md` plan items that its code did not apply.

## Verified source delta (high level)

- Auth: `GET /auth/csrf` returns `200 null` when anonymous; `useSession` handles it; `useLogin`
  gains a student/staff audience gate that revokes a mismatched fresh session; LoginPage passes the
  audience and uses `PasswordInput`.
- Registration UI: `CorUpload` + `PasswordInput` components, `RegisterPage` autocomplete/disabled/
  brand/footer polish, +106 CSS lines.
- Appointments backend: booking-counselor directory, counselor-scoped calendar/slots, calendar
  `available_slots`/`booked_slots`, appointment date filters, standard weekday schedules,
  weekly-schedule enable/delete, soft-delete `is_deleted` column + migration
  `20261024_weekly_sched_softdel`, notification events.
- Appointments frontend: `useAppointments` counselor selection/calendar month/pagination hardening;
  `CalendarGrid`, `BookingModal`, `CounselorAppointmentsPage` updates; event-driven refreshes and
  `counselconnect-toast`.
- Tests: new `scheduled-events.test.cjs`; expanded appointments/registration/session tests; backend
  appointment + auth-flow tests.
- Excluded local artifacts: `charm-paneer-uncommitted-backup.patch`, `image.png`, `.kilo`, `.vscode`,
  `.venv`, `node_modules`, `dist`, `var`, caches, `.env*`, `.ai/CURRENT_TASK.md`.

## Ordered tasks

### 1. Pre-flight (no writes beyond the checkpoint)

- Confirm `git rev-parse HEAD` = `f9abe19` and `git status` contains only the known calls work plus
  the snapshot folder. Stop if unrelated edits exist.
- Confirm the snapshot differs from the top-level only as listed above:
  `git diff --no-index --stat <top-level> <snapshot>` for `backend/app/modules/{auth,accounts,cor_screening,appointments}`, `frontend/src`, `frontend/tests`, `backend/app/tests`, `backend/migrations`, `docs`.
- Record the exact source-only files and the current-only files (calls; `services/realtime.js`).

### 2. Checkpoint the video-call work

- Create `merge/calls-checkpoint` from `main`.
- Stage **explicitly** the calls-related files: `backend/app/modules/calls/**`,
  `backend/app/shared/realtime.py`, `backend/app/config.py`, appointments call hunks,
  `backend/.env.example`, `backend/app/tests/integration/test_calls.py`,
  `frontend/src/features/calls/**`, `frontend/src/components/calls/**`,
  `frontend/src/services/realtime.js`, `frontend/src/pages/ScheduledSessionPage.jsx`,
  messaging socket import, call tests, calls docs/ADR, and `contracts/openapi.json`.
- Commit locally only. Do **not** stage `.kilo/`, the nested snapshot, or unrelated files.

### 3. Build `merge/snapshot-fix` from the base

- `git worktree add <temp-outside-repo> f9abe19`; create branch `merge/snapshot-fix`.
- Copy the snapshot's product files over the worktree, **excluding** the local-artifact list above,
  the nested snapshot folder, `.ai/`, `contracts/openapi.json`, `docs/AUDIO_VIDEO_CALLS.md`,
  `docs/TEAM_SETUP_GUIDE.md`, `docs/WORKFLOWS.md`, and `frontend/src/services/realtime.js`.
- Copy the snapshot's `docs/API_CONTRACT.md`, `APPOINTMENT_SCHEDULING.md`,
  `REAL_TIME_MESSAGING.md`, `SECURITY.md`, `MARKDOWN_UPDATE_GUIDE.txt`, and the new
  `COUNSELOR_FIRST_BOOKING_PLAN.md` as B-side changes; verify no desired docs were deleted.
- Review `git status` in the worktree. Expected: auth/router, auth hooks/pages, registration UI,
  appointment backend/frontend, calendar/booking components, CSS, tests, the new migration, and
  docs. No calls files, no `.ai` churn, no snapshot changes.
- Commit B locally.

### 4. Merge B into the checkpoint

- `git switch merge/calls-checkpoint`; `git merge --no-ff merge/snapshot-fix`.
- Resolve conflicts with this contract:

| File | Required result |
|---|---|
| `backend/app/modules/appointments/service.py` | Keep A's `CallContext`, `_live_window`, `call_context`, `can_call` **and** B's booking/calendar/schedule/filter methods. Use `_live_window` in `session_response`. |
| `backend/app/modules/appointments/schemas.py` | Keep `can_call`; add B's `CounselorBookingOption`, calendar slot types, `StandardWeekdayScheduleRequest`, and new calendar fields. |
| `backend/app/modules/appointments/router.py` | Keep B's new endpoints/events; calls router stays separate. |
| `frontend/src/features/messaging/useScheduledSessions.js` | Keep A's `socketUrl` import from `services/realtime`; add B's event dispatch and deferred close. |
| `frontend/src/features/messaging/index.js` | Keep A's `socketUrl` export. |
| `frontend/src/App.jsx` | Keep B's toast listener; no video route is required (the call panel lives on the session page). |
| `frontend/src/pages/ScheduledSessionPage.jsx` | Keep A's call panel and props. |
| `frontend/tests/scheduled-chat.test.cjs` | Keep A's `can_call` fixtures + call-panel test and B's event tests. |
| Docs | Keep A's call sections/status; add B's registration/appointment wording; keep TEAM_SETUP/WORKFLOWS. |
| `contracts/openapi.json` | Resolve by regeneration, not merge. |
| `.ai/` | Keep A's ADR-034/CURRENT_TASK/ARCHITECTURE/CONTEXT_MAP; do not copy the snapshot's `.ai`. |

### 5. Post-merge fixes

- **Test DB migration:** add `20261024_weekly_sched_softdel` to the migration loader/sequence in
  `backend/app/tests/conftest.py` (the snapshot omits this and would fail on `is_deleted`).
- Add/confirm a migration round-trip check (`upgrade` adds `is_deleted`, `downgrade` removes it) and
  `alembic heads` = `20261024_weekly_sched_softdel`.
- Regenerate `contracts/openapi.json`; verify `scripts/export_openapi.py --check`.
- Update `docs/DATABASE.md` for `is_deleted`; add a note in
  `docs/structure/PROJECT_STRUCTURE.md` that `CounselConnect-test-Registration_Fix/` is a historical
  reference snapshot excluded from builds/tests/imports.
- Update `.ai/CURRENT_TASK.md` with the merge outcome/verification.

### 6. Verification

- Backend with the disposable test DB: full `pytest` plus targeted `test_appointments.py`,
  `test_calls.py`, `test_auth_flow.py`; expect the source's new tests and calls to pass.
- Frontend: `npm test` (source's scheduled-events/appointments/session/registration tests + calls),
  `npm run build`.
- Treat the known calendar date-rot failures (past `2026-09-19` fixture and the UTC/Manila window
  drift) as pre-existing; do not weaken assertions. The snapshot's own plan mentions three such
  failures, so classify them before reporting.
- `python scripts/export_openapi.py --check`.
- `alembic heads`; migration upgrade/downgrade on a disposable schema.
- Manual QA: student/staff login audience mismatch, anonymous CSRF startup, registration upload/
  password UX, counselor selection, calendar month/booked slots, standard weekdays, enable/disable/
  delete, appointment event toasts, and a call between the owning Student and assigned Counselor.
- Fresh read-only HIGH-risk review before acceptance.

## Non-goals

- No history rewrite, no push, no force operations.
- No new features beyond the snapshot and the conflict/migration fixes above.
- No changes to the snapshot folder itself.
- No call-feature regression; the call docs/ADR/OpenAPI/tests remain.

## Risks / notes

- **Auth behavior:** CSRF 200/null and the audience gate are security-relevant; test anonymous,
  student-on-staff-form, staff-on-student-form, and normal flows.
- **Migration:** `is_deleted` is new; the test harness and any deployed DB must apply it. The
  migration is additive and guarded.
- **Snapshot duplication:** the kept reference folder is stale by design; never import/build/test it.
- **Docs:** the snapshot deletes `TEAM_SETUP_GUIDE`/`WORKFLOWS` and predates the calls work; do not
  apply those deletions or copy its `AUDIO_VIDEO_CALLS`.
- **Source completeness:** the snapshot omits the test-fixture migration; do not assume its tests
  are green until the merge fixes run.
