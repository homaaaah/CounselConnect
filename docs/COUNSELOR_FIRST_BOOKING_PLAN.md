# Counselor-first appointment booking plan

**Status:** IMPLEMENTED — phases 1–3 delivered.
**Scope:** Appointment booking modal and its availability API integration (phases 1–3 only).
**Decision:** The Student selects an available Counselor before choosing a date or time.

**Progress note:** The counselor-first wizard, API filters, inactive-Counselor slot filter, appointment refresh events, and all-or-nothing selected-date pagination are implemented. The frontend suite passed (78 tests), the production build passed (74 modules), and Python compilation passed. The MySQL integration suite still needs the isolated test database configured through `COUNSELCONNECT_TEST_DATABASE_URL`.

## Objective

Make the Student booking flow counselor-first while preserving the current slot-based booking contract, server-side authorization, database reservation guarantees, rescheduling rules, and appointment-linked chat lifecycle. The selected availability slot remains the authoritative source for the Counselor, campus, time, supported delivery mode, and face-to-face location.

This plan excludes voice/video calling, file attachments, and appointment database schema changes.

## Current-state findings

- `GET /availability-slots` returns paginated slots with Counselor/campus display data, but has no `counselor_user_id` filter.
- `GET /calendar` aggregates times across all active Counselors for Students and has no Counselor filter.
- There is no Student-facing endpoint that lists only Counselors with bookable availability in a bounded date range.
- Booking and rescheduling submit `availability_slot_id` and `appointment_mode`; the backend derives Counselor, campus, and location from the locked slot and revalidates availability.
- `appointments.counselor_user_id` is required and derived from the chosen slot. The database has active-slot uniqueness and participant/time conflict protections; no new appointment-to-counselor relationship is needed.
- `BookingModal` is shared by new bookings and rescheduling. Student rescheduling may select a different Counselor; Counselor rescheduling is restricted to the assigned Counselor's own slots. These actor-specific behaviors must remain distinct.
- Online appointments already use scheduled text chat. This booking work must not create conversations, alter chat timing, or change appointment outcomes.

## Proposed Student flow

Use these six visible steps, with a progress indicator and working Back navigation:

1. **Choose Counselor** — show only active Counselors with at least one bookable slot in the selected search range; show enough campus/availability context to distinguish choices.
2. **Choose date** — show real available dates filtered to the chosen Counselor.
3. **Choose time and campus** — show concrete slots for the selected date, including campus when that Counselor has multiple locations or same-time slots.
4. **Choose session mode** — offer only modes supported by the selected slot; disable face-to-face when its Guidance Office location is missing.
5. **Review** — display Counselor, campus, Manila-local date/time, mode, and the exact Guidance Office location snapshot for face-to-face.
6. **Submit request** — submit the selected slot and mode, then show the pending-review result.

On back navigation, preserve valid downstream choices. If the Student changes Counselor, date, or slot, clear only choices that depend on the changed value. A refreshed slot may remain selected only when its `slot_id` is unchanged and it remains bookable.

## Implemented API contract

The implementation uses the existing slot-based booking mutation and adds read-only counselor scoping. The API contract and generated OpenAPI document describe the shipped behavior.

### `GET /booking-counselors`

Returns active Counselors to an authorized Student, with only the ID and display name needed for selection. Availability is then loaded for the selected Counselor, so an active Counselor with no current slots receives the normal empty-availability state.

### Counselor-filtered availability

- `GET /calendar` accepts optional `counselor_user_id` and calculates availability for that Counselor only.
- `GET /availability-slots` accepts optional `counselor_user_id`; Student results are scoped to the selected active Counselor and exclude inactive Counselors before count and pagination.
- Counselor reads remain self-scoped, regardless of a supplied Counselor ID.
- Calendar dates use `Asia/Manila`; slot and appointment range filters use aware timestamps. Availability filters apply before count and pagination.

### Booking and reschedule writes

Do not add a Counselor ID to `AppointmentCreateRequest` or `AppointmentRescheduleRequest`. Continue sending only `availability_slot_id` and `appointment_mode`; derive the Counselor from the slot under the existing transactional locks. Revalidate the selected slot inside the write transaction and preserve existing 409 behavior for stale slots and conflicts.

## Data and migration decision

No database migration is planned. Existing availability slots already identify `counselor_user_id`, `campus_id`, time range, delivery mode, and schedule provenance; appointments persist the selected Counselor through their existing required foreign key. Reuse existing indexes where adequate. If query plans show the counselor/range search is too expensive, inspect MySQL `EXPLAIN` and current indexes before proposing a migration. Do not add duplicated Counselor-selection state or a draft booking table for this UI-only flow.

## Compatibility and conflict controls

- **Booking race:** discovery results are hints only. The locked slot validation and unique active reservation remain authoritative.
- **Rescheduling:** preserve the student's 24-hour cutoff, confirmed-only restriction, participant activity guard, and atomic replacement behavior. Students may choose another Counselor only by choosing one of that Counselor's eligible replacement slots. Counselors remain limited to their own replacement slots.
- **Mode/location:** changing the selected slot must recalculate supported `appointment_mode` choices and the campus Guidance Office snapshot. Never carry a face-to-face mode or location from a prior slot without validation.
- **Pagination/completeness:** the Counselor list and slot list must have stable ordering and correct total counts; do not build the Counselor list by aggregating only the first page of slots.
- **Schedule materialization:** date-range discovery must respect the existing 63-day calendar bound and lazy schedule materialization. Avoid unbounded pre-generation or doing repeated all-Counselor materialization on every UI render.
- **Permissions:** only active Students may discover bookable Counselors and create appointments. A hidden UI is not authorization; enforce role and account state on every endpoint.
- **Chat isolation:** confirmation remains independent of conversation creation. The first authorized online-session join continues to create/reuse the appointment conversation.
- **Public identity:** display only the agreed Counselor name and eligibility context; do not expose email, account metadata, or unrelated profile data.

## Existing integration findings and safeguards

These safeguards affect whether counselor-first selection and appointment updates behave consistently. They are separate from the new wizard and preserve the current booking/write contracts.

### 1. Exclude inactive Counselors from Student slot results

**Observed risk:** the Student branch of `GET /availability-slots` filters available slots but does not join/filter the Counselor's active account status. `GET /calendar` separately limits its results to active Counselor IDs. A deactivated Counselor can therefore be missing from the calendar while one of their slots remains in a slot-list response; booking correctly rejects that Counselor later.

**Implemented:** Student slot queries now apply an active Counselor existence predicate before count, ordering, and pagination. Counselor callers remain scoped to their own slots. Transactional active-account validation in booking/rescheduling remains the final authority if an account is disabled after a read.

**Preserved behavior:** no change to slot status, reservation writes, calendar materialization, Counselor self-availability management, or API response shape. Add a regression where a Student sees no slot for an inactive Counselor and where pagination totals exclude it; retain a write-path test that a deactivation race is rejected.

### 2. Refresh appointment records for all appointment state events

**Observed risk:** cancellation and Counselor outcomes publish `session_closed`. The scheduled-session hook refreshes its own session list for every event but currently dispatches `appointment-updated` only for request/session-change/confirmation events. The other participant's appointment record can remain stale until polling.

**Implemented:** the scheduled-session hook now dispatches `appointment-updated` for `session_closed` as well as the existing appointment events. Confirmation and new-request toast behavior remains restricted to their explicit event names; server event names and chat event handling are unchanged.

**Preserved behavior:** do not rename or remove server events, alter commit-before-publish ordering, show duplicate toasts, make REST writes from a WebSocket handler, or change conversation close/timeout rules. Test that `session_closed` refreshes appointment records and still closes the relevant session UI; test that only `appointment_confirmed` produces the Student confirmation toast.

### 3. Treat selected-date pagination as all-or-nothing

**Observed risk:** when fetching every slot page for a selected date, a failure on a later page sets an error but can leave the first page in state. The modal may then allow booking from an incomplete candidate list.

**Implemented:** selected-date results are accepted only when page metadata, item counts, totals, and slot identities are consistent. A failed or inconsistent page clears availability choices for that date, preserves appointment records, and shows a retry action. A complete refresh restores selection.

**Preserved behavior:** keep page size limits, stable API ordering, the existing slot ID selection, and normal availability for results that fit one page. Do not disable the entire appointment records screen or discard already-loaded appointment history when only availability pagination fails. Backend booking validation remains unchanged.

### 4. Restore the Student home booking hook import

**Observed risk:** the Student home page invoked `useAppointments` without importing it, causing a runtime `ReferenceError` when the page rendered.

**Implemented:** import `useAppointments` from the existing appointment feature module. The existing home-page booking regression now exercises this path and passes.

## Delivered integration sequence

The implementation delivered and integrated these safeguards:

1. Kept the Student booking hook and home-page booking regression.
2. Added active-Counselor filtering to Student slot reads and regression coverage.
3. Made selected-date pagination all-or-nothing so incomplete availability cannot remain selectable.
4. Refreshes appointment records for request, confirmation, session-change, and session-close events while keeping toast behavior specific to request and confirmation.
5. Added counselor selection and counselor-scoped calendar/slot reads.
6. Implemented the six-stage wizard with back navigation, dependency resets, slot/mode review, and existing write-path validation.

## Phase 1–3 implementation sequence

1. **Contract and product acceptance:** confirm the six step labels/order, search horizon, campus presentation, empty-state wording, Counselor display fields, and behavior for Student versus Counselor rescheduling. Update the planned API proposal to AGREED before parallel frontend/backend implementation.
2. **Backend discovery/filtering:** add and test the paginated eligible-Counselor query; add counselor filtering to calendar and slot reads; enforce role, active status, schedule/block/slot eligibility, range limits, count correctness, and self-only Counselor scope. Keep booking writes unchanged.
3. **Frontend wizard:** update `BookingModal` and `useAppointments` to use counselor-first discovery and filtered calendar/slot reads. Preserve selected slot identity and actor-aware rescheduling. Do not change appointment list/dashboard data fetching.
4. **Contract artifacts:** update `docs/API_CONTRACT.md`, `contracts/openapi.json`, and `docs/APPOINTMENT_SCHEDULING.md` from the verified implementation.

## Acceptance criteria and regression coverage

### Backend/API

- Active Student sees only Counselors with eligible future availability in the requested range; inactive, empty, blocked, past, reserved, or conflicting availability does not create a false eligible result.
- Counselor discovery is paginated with a correct total and stable order; invalid or overlong ranges return the documented validation error.
- Student calendar and slot results are scoped to the selected Counselor; same-time slots across campuses remain distinct concrete choices.
- Student slot queries exclude inactive Counselors before totals and pagination; booking still rejects an account disabled after discovery.
- Counselor reads remain self-scoped even if another `counselor_user_id` is supplied; pending Students and Guidance Staff remain denied.
- Forged or stale slot IDs cannot book for a Counselor other than the one encoded by the slot; double booking and participant conflicts remain prevented.
- Existing booking, confirmation, rejection, cancel, reschedule, mode-change, location snapshot, and online session tests remain green.

### Frontend

- New booking enforces the counselor-first progression and displays clear loading, empty, retry, and stale-slot states.
- Failed/incomplete selected-date pagination cannot leave a partial list selectable; a complete retry restores selection.
- Back navigation preserves valid selection; changing Counselor/date/slot clears dependent state and does not submit an old slot.
- Mode options and review details match the currently selected slot; face-to-face requires the configured location.
- Submit uses the existing request shape and displays pending Counselor review on success.
- Student rescheduling may change Counselor when allowed; Counselor rescheduling cannot escape self-scope; existing 24-hour and activity restrictions are surfaced without weakening server checks.
- Existing appointment dashboards, status filters, calendar behavior, notification events, and scheduled chat UI are unchanged.
- `session_closed` refreshes both participants' appointment records while retaining session closure behavior; request/confirmation toast rules do not broaden.

### Verification before release

- Run focused backend unit and MySQL integration tests for discovery scope, eligibility, pagination, authorization, and concurrent booking.
- Run focused frontend tests for the six-step wizard, selection reset/back behavior, booking and both reschedule roles.
- Run the full frontend suite/build, backend suite against MySQL 8.4, OpenAPI snapshot check, and `git diff --check`.
- Review MySQL query plans for the discovery endpoint against representative slot volumes before approving release; add an index only if the measured plan requires it.

## Explicit non-goals

- Audio/video calling, recordings, transcripts, or summaries.
- File attachments or changes to messaging retention.
- New appointment status values, persistent booking drafts, or schema changes.
- Changes to Counselor approval, cancellation, rescheduling, session timeout, or session outcome policy.
