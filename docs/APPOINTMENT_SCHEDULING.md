# CounselConnect — Appointment Scheduling

## Contract

Scheduling follows the approved **CounselConnect Appointment Scheduling Process Flow** (2026-09-10), reference Flowchart V1 page 4. Availability comes from Counselor weekly schedules plus temporary blocks, Students request slots, and Counselors review requests and record outcomes.

**1. Counselor sets weekly availability.** A Counselor creates a fixed weekly schedule that repeats until changed or disabled. For each working period the Counselor selects the day, campus, time range, slot duration (15–240 minutes, whole slots), and supported mode (`ONLINE`, `FACE_TO_FACE`, or `BOTH`). `ONLINE` needs no physical location. `FACE_TO_FACE`/`BOTH` load the campus Guidance Office location: without a configured location the system rejects the face-to-face availability (`GUIDANCE_OFFICE_REQUIRED`) and nothing is saved; the Counselor must configure the location or correct the schedule before retrying. Active weekly periods may not overlap each other for the same Counselor. Valid schedules persist as recurring university-local (`Asia/Manila`) definitions.

**2. Counselor blocks unavailable time.** Instead of changing the weekly schedule, a Counselor creates a temporary block: a date or datetime range, optionally whole-day, with an optional short reason (≤ 255 characters). The system rejects a block that would overlap an existing `PENDING` or `CONFIRMED` appointment (`BLOCK_CONFLICT`) — the affected appointment must be resolved first; a block never cancels, rejects, reschedules, or moves an appointment. Valid blocks save without touching the recurring schedule. When generating and calculating bookable slots, the system excludes blocked periods, existing appointments, and past times. Weekly-schedule changes apply to future availability. Matching future `AVAILABLE` slots adopt the active schedule's supported mode when availability is materialized; leftover available slots attached to the replaced, inactive schedule are excluded from calendars and booking. `RESERVED` slots and existing appointments remain unchanged.

**3. Student selects an appointment.** An `ACTIVE` Student searches future available slots. The system displays each slot's campus, date, time, supported modes, and Guidance Office location. The Student chooses a slot and a supported mode and submits the request.

**4. System validates the request.** The system re-checks that the slot is still available, the mode is supported, and no participant conflict exists. A slot whose Manila date has already passed is rejected with `APPOINTMENT_DATE_PASSED`; a slot whose start time has already passed today is rejected with `APPOINTMENT_TIME_PASSED` (both 409, original reservation untouched on reschedule). Other failures inform the Student the selection is unavailable or incompatible (`SLOT_UNAVAILABLE`, `MODE_INCOMPATIBLE`, `SCHEDULE_CONFLICT`, `GUIDANCE_OFFICE_REQUIRED`) and returns to the available slots. On success the system atomically reserves the slot and creates a `PENDING` appointment. `ONLINE` keeps `meeting_location` empty; `FACE_TO_FACE` copies the current campus Guidance Office location into `appointments.meeting_location` as a booking-time snapshot — later campus-location edits do not alter the existing appointment.

**5. Counselor reviews the request.** The assigned Counselor reviews the request, schedule, and mode. Rejection sets `REJECTED`, optionally with a note (≤ 500 characters), and releases the slot; the Student may then choose another slot or mode. Approval sets `CONFIRMED` (denied after the scheduled start).

**6. Actions after confirmation.** Cancellation sets `CANCELLED` and releases the future slot. Students may cancel or reschedule only until 24 hours before start; the assigned Counselor is unrestricted by that cutoff. Rescheduling (`CONFIRMED` only) selects a replacement slot and supported mode, returns the appointment to `PENDING`, and replaces the location snapshot atomically. Any participant join/message activity prevents rescheduling. Before start and before chat activity, the assigned Counselor may change to another mode supported by the same slot while keeping the appointment `CONFIRMED`. A failed change leaves the original reservation intact.

**7. Online appointment.** At the scheduled start, the system authorizes and opens a dedicated appointment Live Chat linked to the appointment (requirements in "Online appointment integration"; Live Chat transport/joining remains a separate unimplemented feature).

**8. Face-to-face appointment.** The system displays the saved campus Guidance Office location snapshot, and the Student attends onsite at that location.

**9. Session outcome.** After either mode, the system records the session outcome. Only the assigned Counselor sets outcomes, only from `CONFIRMED`, and only once the scheduled start is reached; face-to-face outcomes are entered manually by the Counselor. If the session finishes, the status becomes `COMPLETED`; if the Student is absent, `NO_SHOW`. Terminal transitions close the linked conversation when applicable. A `CANCELLED`, `COMPLETED`, or `NO_SHOW` appointment is considered closed.

## Appointment status guide

| Status | Meaning |
|---|---|
| `PENDING` | Request created; its slot is reserved while awaiting Counselor review. |
| `REJECTED` | The Counselor declined the request and the slot was released. |
| `CONFIRMED` | The Counselor approved the appointment. |
| `CANCELLED` | The appointment was cancelled and its future slot was released. |
| `COMPLETED` | The scheduled session finished. |
| `NO_SHOW` | The Student did not attend the scheduled session. |

## Online appointment integration

- A confirmed `ONLINE` appointment may create or reuse exactly one dedicated conversation when the scheduled start is reached.
- The linked conversation uses `conversation_type = APPOINTMENT`.
- The appointment and conversation must contain the same Student and Counselor.
- `appointments.conversation_id` is nullable and unique.
- A `FACE_TO_FACE` appointment must not have an appointment-linked conversation.
- `GENERAL` Live Chat and `SOS` conversations remain separate from scheduled appointment conversations.
- Ending the online conversation returns control to the appointment workflow; only an authorized appointment outcome transition sets `COMPLETED` or `NO_SHOW`.

## Calendar implementation

The authenticated `#appointments` screen presents a calendar of real dates. `GET /calendar` materializes concrete slots from active weekly schedules for the requested range (≤ 63 days), then returns calendar-date metadata, blocked dates, and generated slot availability, identified by `Asia/Manila`; blocked-period exclusion happens at slot generation. Each day carries `is_past`; `available_times` contains sorted, distinct Manila start times from actual future `AVAILABLE` slots across the full requested range, excluding temporary time blocks and each owning Counselor's whole-day blocks. Counselor calendars use only their own slots; Student calendars use active Counselors. Multiple slots at the same start time count as one available time. Saturday and Sunday remain selectable when a Counselor has configured availability for them; a weekend without availability remains unselectable. Days with no slots return an empty list, never default business-hour placeholders. Fully past days return no available times, and today keeps only Manila times still ahead of now. The frontend renders past days as unselectable and drops already-started slots from the list between refreshes. Calendar counts and selected-day time buttons also remove elapsed starts every second and on window focus, without making a request or renewing the session; an empty count displays "No times left". Counselors use `POST /calendar/blocks` and `DELETE /calendar/blocks/{blocked_date}` for whole-day blocks. The frontend refreshes when the screen opens, after block changes, and on date changes, plus a background refresh every 60 seconds that does not extend an authenticated session; the appointment API remains the authoritative booking and conflict boundary.

## Implemented availability management endpoints

Weekly schedules and temporary blocks are fully implemented (`GET /weekly-schedules`, `POST /weekly-schedules`, `POST /weekly-schedules/{weekly_schedule_id}/replace`, `DELETE /weekly-schedules/{weekly_schedule_id}`, `GET /availability-blocks`, `POST /availability-blocks`, `DELETE /availability-blocks/{availability_block_id}`), and the counselor appointments screen provides management forms for both: a recurring weekly schedule form (campus, day, local time range, slot duration, mode) and a temporary unavailable-time form with a list of existing blocks. Schedule editing uses the atomic replacement endpoint: the previous active definition is deactivated only when the validated replacement is ready. Matching future unreserved slots adopt the replacement mode on materialization, while stale slots linked to the inactive definition no longer appear; reserved slots and existing appointments remain unchanged. The remaining scheduling endpoints are listed in `docs/API_CONTRACT.md`.

## V1 boundary

- Recurring weekly schedules with concrete slot materialization on demand; no appointment-history table.
- Availability generation may accept a time range and slot duration but persists concrete slots (`POST /availability-slots` still supports manual concrete batches of 1–200 slots).
- Status transitions and slot reservation/release must be atomic and auditable.
- Mode compatibility and face-to-face location availability are validated server-side.
- Guidance Staff has no appointment or campus-location-management access.
- No separate meeting-platform integration; scheduled online counseling uses CounselConnect Real-Time Messaging.

## Required tests

- Available request and concurrent/double-book attempt.
- `ONLINE`, `FACE_TO_FACE`, and `BOTH` slot compatibility, including forbidden combinations.
- Face-to-face-capable availability denied when the campus Guidance Office location is missing.
- Correct face-to-face location snapshot and protection from later campus-location changes.
- Pending review and each allowed/forbidden appointment transition.
- Ownership and role access, including Guidance Staff denial.
- Cancel/reschedule slot release and replacement-mode/location revalidation.
- Weekly-schedule constraint enforcement (day, time range, duration bounds, mode enum, overlap, exact duplicate, foreign keys).
- Availability-block overlap with active appointments denied; block deletion.
- Slot materialization from weekly schedules excludes blocked periods and duplicates.
- Online conversation denied before confirmation or scheduled start.
- Appointment/conversation Student and Counselor mismatch denial.
- Face-to-face conversation-link denial and one-conversation-per-appointment enforcement.
- Separation of `GENERAL`, `APPOINTMENT`, and `SOS` conversations.
- UTC persistence and `Asia/Manila` display.

## Implemented scheduling flow

The scheduling UI is at `#appointments`, available from the signed-in navigation to active Students and Counselors. Student sign-in opens Student services with an appointment link. Guidance Staff and pending/expired Students cannot load appointment data. The reference is **Flowchart V1, page 4 (Appointment Scheduling)**.

- Counselor sets recurring university-local availability through weekly schedules (day 1–7 ISO, campus, local time range, 15–240-minute slot duration, mode). Slots are materialized lazily from active schedules when a calendar/slot search needs them, skipping availability-blocked periods and already-materialized times; manual concrete batch creation remains available. Counselor availability cannot overlap across campuses.
- Students filter future slots by campus, Philippine date, and mode; requesting a slot creates `PENDING`. The owning Counselor can confirm or reject a pending request. Rejection optionally includes a note of at most 500 characters.
- Owner Student or assigned Counselor can cancel `PENDING` or `CONFIRMED`. They can reschedule `CONFIRMED` to a different future available slot; the same appointment returns to `PENDING` for review. A Counselor can select only their own replacement slots. A Student can select another Counselor. The replacement mode and campus location are revalidated and its location snapshot replaces the previous booking snapshot atomically. A linked online session prevents rescheduling.
- Only the assigned Counselor records `COMPLETED` or `NO_SHOW`, from `CONFIRMED` and once the scheduled start has been reached. Confirmation after the start is denied. Students cannot cancel or reschedule inside 24 hours of the scheduled start; Counselors retain the authorized action.
- User-row locks in ascending ID order serialize participant conflicts; subsequent appointment, ordered slot, and campus locks revalidate current state. The generated unique active-slot constraint remains the database backstop. Failed replacement requests leave the original reservation intact. Terminal transitions release the reservation; searches exclude past slots.
- Counselor may update a nonblank Guidance Office location. Existing face-to-face snapshots remain unchanged. Missing location blocks face-to-face-capable slot creation and face-to-face booking/rescheduling.
- Lists are scoped to the acting Student or assigned Counselor, paginated at 20 by default (maximum 100), and returned with `Cache-Control: no-store`. Both appointment screens provide status filters for `CONFIRMED`, `PENDING`, `COMPLETED`, `NO_SHOW`, `CANCELLED`, and `REJECTED`, so cancellation history remains visible to both participants and a Student can read the Counselor's rejection note. State changes use the existing cookie/CSRF controls and minimal audit events, with no confidential content copied into audit metadata.
- Dates persist in UTC and serialize with `Z`; form inputs and displays use `Asia/Manila`, independent of the browser's timezone. Refresh is explicit; the appointments screen additionally uses a background refresh interval that never renews session activity.

**Scheduled Live Chat boundary:** confirmed online appointments appear in an appointment-derived launcher. The lobby opens 30 minutes before start. Confirmation does not create a conversation; the first explicit join at or after start creates or reuses the single appointment conversation. REST persists and retrieves ordered messages, while WebSockets deliver committed events. At slot end plus the configured 15-minute grace period, the worker closes an open conversation with `TIMEOUT` without changing the `CONFIRMED` appointment outcome.

**UI boundary:** weekly-schedule and availability-block management forms are implemented on the counselor appointments screen, with backend audit events. The scheduled-session page provides lobby, explicit join, durable text messaging, reconnection catch-up, and Counselor outcome controls. Closed history is Counselor-only until retention cleanup.

## Pending policy and integration

Slot duration/buffer defaults, booking horizon for slot materialization (currently the requested calendar/slot-search range), automatic slot-generation jobs, and detailed no-show policy.

### Slot-list pagination

`GET /availability-slots` excludes counselor-owned whole-day blocks (using the slot start date in Asia/Manila) and overlapping temporary time blocks before counting and paginating. `total` counts all matching slots, including when the requested page is empty. A block belonging to one Counselor never excludes another Counselor's slots. Existing role scope, mode, campus, and date filters remain in effect.

When a Student chooses a calendar date, the frontend retrieves every page of slots for that date (the endpoint maximum is 100 per page). If several concrete slots share a displayed start time, the Student chooses the counselor and campus before submitting the selected `availability_slot_id`; a background refresh retains a compatible chosen appointment mode.
