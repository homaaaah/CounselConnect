# CounselConnect - Current Task

**Status:** ACTIVE
**Task:** Review latest frontend updates; verify all backend-frontend API connections, data fetching, CRUD, loading/error handling; fix confirmed defects, with priority on the Appointment section.

## Objective

Every frontend data-fetching surface connects to the documented FastAPI backend contract and displays correct data; confirmed connection/data-fetch defects are fixed without altering unrelated behavior.

## Route

`whole-system-review` with targeted `appointments` and `messaging` routes as needed.

## In scope

- Frontend services/features/pages calling the backend: appointments, messaging, SOS, wellness, dashboard, registration, auth.
- API client configuration (base URL, envelopes, error handling).
- Appointment section fetching/display (priority).
- Backend route definitions where mismatch is suspected.

## Out of scope

- Redesigns, new features, backend business-rule changes, schema migrations.
- Live Chat transport implementation, dashboard user-count endpoint (known placeholders).

## Acceptance criteria

1. All frontend API calls match existing backend routes (method, path, payload, envelope).
2. Appointment calendar/list/detail fetching and display render real data or a correct error/empty state.
3. CRUD flows that exist on both ends still function (where testable).
4. Loading and error states handled; no silent console errors on broken calls.
5. Existing frontend tests plus focused new tests for any fix pass.

## Planned verification

- Run frontend test suite and build.
- Run backend test suite (expect skips without MySQL test DB).
- Static contract comparison of frontend calls vs backend routers.
- Live read-only checks through the Vite proxy if feasible.

## Unresolved human decisions

- None yet.

## Sequential fixes ? 2026-09-15

User authorized fixes one at a time. First implementation: backend slot-list filtering and pagination.

- Moved counselor-owned Manila whole-day and overlapping time-block exclusions into the repository query before count/offset/limit.
- Removed service filtering that discarded valid slots and overwrote the total.
- Preserved existing role/status and campus/mode/date filters; no schema change.
- Added six service-unit cases and three MySQL integration cases covering totals, page boundaries, overlapping blocks, owner scope, and Manila midnight.
- Verification: 10 focused unit tests passed; 57 MySQL integration cases skipped because COUNSELCONNECT_TEST_DATABASE_URL is unset. MySQL SQL compilation and git diff --check passed. Database execution remains unverified.
- Next separate fix: booking modal pagination and selection of multiple slots sharing a start time. Other review findings remain open.
- Existing frontend/debug/live-test changes were preserved.

Second implementation: selected-date booking slots and shared start-time selection.

- The appointment hook requests up to 100 slots per page and retrieves all remaining pages for a calendar-selected date.
- The booking modal now offers every counselor/campus slot at the selected time and submits the explicitly selected slot ID.
- A background refresh preserves a still-compatible `ONLINE` or `FACE_TO_FACE` selection; choosing a new time resets to the appropriate default.
- Added frontend regressions for a 101-slot selected date, counselor selection, and mode preservation.
- Verification: 41 frontend tests passed; production build passed; `git diff --check` passed.
- Next separate fix: make appointment records fetch independently so calendar or availability errors do not hide records.

Third implementation: independent appointment-record fetching and display.

- Calendar, campuses, slots, records, weekly schedules, and availability blocks now load concurrently with independently handled results.
- A calendar or availability failure no longer prevents `GET /appointments` from completing or clears records already displayed.
- Records retain their own loading/error state, so background availability refreshes do not hide the records list.
- Added a regression for a calendar failure with successful appointment records.
- Verification: 42 frontend tests passed; production build passed; `git diff --check` passed.
- Next separate fix: align weekend schedule creation with the calendar, which currently does not permit Saturday/Sunday booking.

Fourth implementation: weekend availability consistency.

- The calendar now returns scheduled Saturday/Sunday times while retaining `is_weekday` as descriptive metadata.
- The frontend permits a weekend date only when it contains actual available times; empty weekends remain unavailable.
- Replaced the misleading fixed Monday–Friday business-hours label with counselor-configured availability wording.
- Added backend and frontend Saturday-availability regressions.
- Verification: 5 focused backend calendar tests and 43 frontend tests passed; production build and `git diff --check` passed.
- Next separate fix: replace weekly schedules atomically so valid edits do not conflict with the currently active schedule.

Fifth implementation: atomic recurring weekly-schedule replacement.

- Added `POST /weekly-schedules/{weekly_schedule_id}/replace`; it locks the active owned definition, validates the replacement while excluding that definition from overlap detection, then deactivates the old definition and creates or reactivates the replacement in one transaction.
- The counselor edit form now makes that single request, so it cannot create a new schedule and then fail before deactivating the old one. Existing concrete slots and appointments stay attached to their original schedule definition.
- Reusing an identical inactive definition respects the existing unique database constraint while retaining history.
- Updated the API contract, appointment scheduling documentation, and generated OpenAPI snapshot.
- Verification: 9 focused backend tests passed; 58 MySQL integration tests skipped because `COUNSELCONNECT_TEST_DATABASE_URL` is unset. All 43 frontend tests, the OpenAPI snapshot check, the production build, and `git diff --check` passed.
- Next separate fix: remaining appointment review findings, beginning with counselor-side availability-block display and recovery behavior.

Sixth implementation: availability-block display and recovery.

- Availability-block requests now have their own loading and error state, separate from calendar, slots, and appointment records.
- The counselor screen shows a loading state, an explicit empty state, a specific API error, and a retry control. Existing blocks remain visible if a background refresh fails.
- Added a frontend regression that verifies a failed block-list request leaves counselor records visible and that the list appears after retry.
- Verification: all 44 frontend tests, the production build, and `git diff --check` passed.
- Next separate task: configure a MySQL test database and run the skipped appointment integration cases; then continue cross-feature API/data-display review.

Seventh implementation: registration and enrollment-verification data recovery.

- The registration form now preserves successfully loaded campus/program reference data, identifies a failed lookup, and offers a retry instead of showing unexplained empty required selectors.
- The reviewer console now loads pending applications and history independently. A failure in one no longer clears the other; each view has its own loading/error/retry state.
- Added frontend regressions for registration reference-data recovery and reviewer-history recovery while a pending queue remains visible.
- Verification: all 46 frontend tests, the production build, and `git diff --check` passed.
- Unresolved authorization/workflow gap: project rules allow Guidance Staff to review assigned COR cases, but the current API/UI permit only Counselors and contain no assignment workflow. Do not grant Guidance Staff broad review access without an approved assignment source and scope.
- Next separate task: configure a MySQL test database and run the skipped appointment integration cases; then continue cross-feature API/data-display review.

Eighth implementation: assigned Guidance Staff COR review workflow.

- Counselors can retrieve active Guidance Staff and assign a pending verification case through the reviewer console.
- Guidance Staff now reaches the reviewer screen after staff login. Backend queue, history, COR preview, and decision actions are scoped to the assigned case; Counselors retain full review scope.
- Reused the existing `assigned_guidance_staff_user_id` field and its index, so no migration was required. Updated the contract, registration documentation, and generated OpenAPI snapshot.
- Verification: 47 frontend tests passed; 21 focused backend auth/security tests passed and 19 database-dependent cases skipped because the test MySQL database is not configured. Production build, OpenAPI snapshot check, and `git diff --check` passed.
- Next separate task: configure a MySQL test database and run the skipped appointment and verification integration cases; then continue cross-feature API/data-display review.
