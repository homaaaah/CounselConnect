# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** Implement the counselor-first six-stage Student appointment booking flow.
**Route:** `appointments` + `ui-refactor` + `api-or-schema`.

## Contracts to preserve

| Invariant / capability | Owning contract and code | Regression coverage |
|---|---|---|
| Booking still submits the selected concrete slot ID and supported mode to the existing create/reschedule mutation | `BookingModal`, `AppointmentsService.book/reschedule` | Appointment frontend and API tests |
| Calendar/slot counselor filters only narrow active availability; server booking validation remains authoritative | appointment router/service/repository | Appointment integration tests |
| Counselor calendar and booked-date indicator remain unchanged | `CalendarGrid`, `AppointmentsService.calendar` | Appointment frontend/API tests |

- Compatible booking mutation path and payload: `POST /appointments` or `POST /appointments/{appointment_id}/reschedule` with `availability_slot_id` and `appointment_mode`.
- Navigation: counselor → date → time/campus → mode → review → submit; back navigation preserves valid later choices and upstream changes clear dependents.
- Intentional behavior change: Student booking is counselor-first; new authenticated read filters scope calendar and slot results.
- Voice/video calls and file sharing remain out of scope under project rules.

## Result

- Added an active-Counselor booking selector and counselor-scoped calendar/slot reads.
- Implemented counselor → date → time/campus → mode → review → submit with progress, backward navigation, and dependency resets.
- Added visible loading, empty, retry, stale-slot, and server-conflict states. A stale selected campus is not silently replaced by another slot.
- Kept the existing create/reschedule API payloads and server-side booking validation intact.
- Kept Counselor calendar booked-time indicators scoped to the Counselor dashboard.
- Updated API, appointment, OpenAPI, and current-task documentation.

## Verification

- `node --test frontend/tests/*.test.cjs`: passed (77 tests).
- `npm.cmd --prefix frontend run build`: passed (74 modules).
- Python compile check and `git diff --check`: passed.
- Appointment integration tests were invoked but skipped (62 tests) because `COUNSELCONNECT_TEST_DATABASE_URL` is not configured in this checkout. Database-backed filter/auth behavior still needs that isolated MySQL test database.
