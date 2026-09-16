# CounselConnect - Current Task

**Status:** COMPLETE
**Task:** Implement the approved appointment-linked Scheduled Live Chat plan across MySQL schema, appointment/messaging services, REST/WebSocket transport, maintenance jobs, and frontend session UI.

## Objective

Confirmed online appointments provide a safe time-gated lobby and durable text chat without creating a conversation at confirmation or inferring an appointment outcome from timeout.

## Route

`appointments` and `messaging`, with auth-session and frontend-shell integration.

## In scope

- Migration and bidirectional appointment/conversation integrity.
- Appointment timing, cutoff, mode-change, outcome, reminder, and timeout rules.
- Durable REST messages/cursor history plus authenticated delivery-only WebSockets.
- Appointment-derived launcher, lobby/chat UI, reconnect catch-up, and session-expiry warning.

## Out of scope

- General/SOS chat UI, attachments, read receipts, Redis/multi-process fan-out, audio/video, transcripts, and summaries.

## Acceptance criteria

1. Confirmation creates no conversation; first authorized join at start creates exactly one.
2. REST remains durable and WebSockets publish only committed events with session/origin reauthorization.
3. Timeout closes chat without changing `CONFIRMED`; only Counselor outcomes complete/no-show.
4. Student 24-hour cutoff and Counselor pre-start mode conversion are enforced server-side.
5. Closed history/retention and background activity session rules are enforced.
6. Frontend tests/build and backend tests pass; MySQL tests must run before readiness is declared.

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

Ninth implementation: recurring-availability calendar synchronization.

- Calendar and slot-list queries now exclude available slots attached to an inactive, replaced weekly schedule. One-off slots remain unaffected.
- Materialization continues to add the replacement's future slots, so a Wednesday 08:00–15:00 schedule with 60-minute `BOTH` availability appears as seven Manila-local starts on the next calendar refresh.
- Existing reservations and appointments retain their original slot records and remain unchanged.
- Verification: 18 focused appointment unit tests passed; frontend production build passed; 61 MySQL integration tests skipped because `COUNSELCONNECT_TEST_DATABASE_URL` is unset.

Tenth implementation: verification-decision email outcome reporting.

- Registration approval and rejection now wait for the SMTP server to accept the notification, returning `SENT`, `NOT_CONFIGURED`, or `FAILED` to the reviewer.
- A mail failure never reverses the already committed enrollment decision. The reviewer receives a warning with the sender-setting follow-up instead of an inaccurate queued-email message.
- Verification: 3 focused notification tests and 12 reviewer frontend tests passed; OpenAPI snapshot and frontend production build passed. Database-backed tests remain skipped without the dedicated MySQL test database.

Eleventh implementation: appointment cancellation and rejection history visibility.

## Contracts to preserve

| Invariant / user capability | Owning contract and code | Regression test |
|---|---|---|
| Appointment lists remain scoped to the signed-in Student or assigned Counselor and filtered server-side by the selected status. | `docs/APPOINTMENT_SCHEDULING.md`, `backend/app/modules/appointments/repository.py`, `frontend/src/features/appointments/useAppointments.js` | `frontend/tests/appointments.test.cjs` |
| Rejection notes returned by the appointment API remain visible to the owning Student. | `backend/app/modules/appointments/schemas.py`, `frontend/src/pages/student/StudentAppointmentsPage.jsx` | `frontend/tests/appointments.test.cjs` |

- Compatible API methods, paths, payload fields, and response shapes: `GET /appointments?status=<APPOINTMENT_STATUS>` and the existing `AppointmentResponse` fields.
- Navigation and actions that must remain available: the existing Confirmed, Pending, and Completed filters, pagination, Counselor review controls, and student cancellation/reschedule constraints.
- Intentional behavior change explicitly authorized by the user: both appointment screens expose `NO_SHOW`, `CANCELLED`, and `REJECTED` status filters. Cancelled records remain in the Counselor's history and rejected records expose the existing Counselor note to the Student.
- Verification: 23 focused frontend appointment tests and the production build passed. Database integration remains unverified because `COUNSELCONNECT_TEST_DATABASE_URL` is unset.
