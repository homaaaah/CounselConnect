# CounselConnect — Current Task

**Status:** COMPLETED
**Risk class:** HIGH (MySQL schema/migrations, appointment reservation boundaries)
**Mode:** Verify & gap-fill + fix-it pass + pending-decision resolution (2026-09-10); all work committed and pushed.

## Final state (2026-09-10)

Branch `database/recurring-schedules-and-blocks` pushed to origin (HEAD `f8edb3a`), 7 logical commits: schema/migrations → CONTRIBUTING restore → service layer → endpoints → tests → frontend UI → ADRs/docs. Backend 125/125 on MySQL 8.4; frontend build clean + 16/16 tests; OpenAPI snapshot regenerated and `--check` verified; working tree clean.

## Delivered across this task series

1. Database audit + gap-fill (booking-block exclusion, list filtering, lock serialization, hardened migration tests, service-boundary tests).
2. `GET /availability-blocks` endpoint + counselor schedule/block management UI + live React/HTTP test rewrite.
3. Environment fixes (venv rebuild, execution policy, CONTRIBUTING restore, stray-file cleanup).
4. ADR-020 (supersedes ADR-007) and user-approved ADR-021..027 resolving P02/P04–P08; cross-references updated in code, docs, and OpenAPI; `FR-APPT-01` updated.
5. OpenAPI snapshot regenerated with all new endpoints.

## Delivered this pass

1. **Missing `GET /availability-blocks`** (real gap found mid-task): added repository `availability_blocks()`, service `list_availability_blocks()`, router `GET /availability-blocks` (counselor-only, own rows) following the `list_weekly_schedules` pattern.
2. **Counselor management UI**: `WeeklyScheduleSection` (campus/day/local-time/duration/mode form with whole-slot and Guidance-Office warnings; disable button) and `AvailabilityBlocksSection` (create/remove temporary blocks with future-time validation) on `AppointmentsPage`; hook fetches both for counselors only, passes `role`, `mutate` now sends no body for DELETE.
3. **Live-frontend test drift fixed**: rewrote `live-appointments.cjs` to drive the real current UI (weekly-schedule form → materialized slots → student books face-to-face → counselor confirms → cancels); updated the Python harness's stale post-conditions (slots now materialize from the schedule; all AVAILABLE + `weekly_schedule_id` provenance).
4. **Venv rebuilt**: `backend/.venv` recreated with system Python 3.11.6, requirements installed, all suites run through it.
5. **`.ai/CONTRIBUTING.md` restored** from `docs/contributing-guide` branch (file had been deleted from the working tree).
6. **Lock asymmetry fixed**: `delete_availability_block` now takes the counselor user-row lock (`_participants`) like create.
7. **Housekeeping**: `debug.log` removed; PowerShell `CurrentUser` execution policy set to `RemoteSigned` (npm works).
8. **Docs updated**: API_CONTRACT.md endpoint table now lists weekly-schedule/availability-block/calendar endpoints; APPOINTMENT_SCHEDULING.md UI-boundary reflects the implemented management forms.

## Verification (2026-09-10)

- Backend full suite (rebuilt venv, MySQL 8.4 disposable schemas): **125/125 passed** — includes the live React/HTTP flow.
- Frontend: `tsc -b && vite build` clean; `npm test` 16/16.
- Backend compile OK; zero leftover test schemas; dev DB at `20260910_recurring_schedules`.
- Final-state check: `GET /availability-blocks` covered by the live flow (counselor block list renders).

## Files changed this pass

Backend: `router.py`, `service.py`, `repository.py`, `test_appointments_frontend.py`. Frontend: `AppointmentsPage.tsx`, `useAppointments.ts`, `features/appointments/index.ts`, `tests/live-appointments.cjs`. Docs: `API_CONTRACT.md`, `APPOINTMENT_SCHEDULING.md`. Meta: `.ai/CURRENT_TASK.md`, restored `.ai/CONTRIBUTING.md`.

## Unresolved human decisions (updated 2026-09-10)

1. Commit/branch strategy for the accumulated uncommitted work (CONTRIBUTING: `database/<task>` etc.; isolate before new tasks) — **RESOLVED 2026-09-10**: user approved committing on `database/recurring-schedules-and-blocks` with logical commits; coordinate with the `frontend/migrate-to-javascript` owner before they rebase.
2. ~~ADR-007 supersession~~ **RESOLVED 2026-09-10**: superseded by new ADR-020 (recurring weekly schedules + temporary blocks); `FR-APPT-01` wording updated to match.
3. ~~`FR-APPT-01` wording~~ **RESOLVED** with ADR-020.
4. ~~ADR-P04 policies~~ **RESOLVED 2026-09-10**: user approved recommended policies → ADR-021 (60-day horizon, lazy materialization, 24h student cutoff, no reminders in v1, manual no-show, 15-min join window).
5. ~~ADR-P02 Live Chat transport~~ **RESOLVED 2026-09-10**: user approved → ADR-022 (native FastAPI WebSocket, in-memory registry, ADR-008 retention; implementation still pending).
6. ~~ADR-P05 COR details~~ **RESOLVED** → ADR-024 (ratifies implemented PDF-only/10 MB behavior).
7. ~~ADR-P06 expression library~~ **RESOLVED** → ADR-025 (face-api.js, 7 labels, ≥60% confidence, opt-in).
8. ~~ADR-P07 manual-resource rules~~ **RESOLVED** → ADR-026 (single Counselor approval, 5/10/25 MB attachment caps).
9. ~~ADR-P08 assistant~~ **RESOLVED** → ADR-027 (deterministic retrieval, no LLM in v1).
10. ADR-P03 content half (SOS question wording/thresholds — guidance-office approval) — still pending.
11. ADR-P09 (Capacitor credential transport, production email fallback) — still pending.
