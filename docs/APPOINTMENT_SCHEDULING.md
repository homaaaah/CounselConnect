# CounselConnect — Appointment Scheduling

> The counselor-first booking flow and its API additions are implemented. The implementation plan and acceptance criteria are documented in [COUNSELOR_FIRST_BOOKING_PLAN.md](COUNSELOR_FIRST_BOOKING_PLAN.md); server-side booking validation remains authoritative.

## Contract

Scheduling follows the approved **CounselConnect Appointment Scheduling Process Flow** (2026-09-10), reference Flowchart V1 page 4. Availability comes from Counselor weekly schedules plus temporary blocks, Students request slots, and Counselors review requests and record outcomes.

**1. Counselor sets weekly availability.** A Counselor creates a fixed weekly schedule that repeats until changed or disabled. For each working period the Counselor selects the day, campus, time range, slot duration (15–240 minutes, whole slots), and supported mode (`ONLINE`, `FACE_TO_FACE`, or `BOTH`). The Counselor editor defaults new schedule times to 8:00 AM–4:00 PM for standard weekday coverage. The explicit standard-weekdays action creates or restores Monday–Friday schedules at those hours for the selected campus, duration, and mode; it validates all five days before making changes and rejects the complete batch if an existing schedule conflicts. `ONLINE` needs no physical location. `FACE_TO_FACE`/`BOTH` load the campus Guidance Office location: without a configured location the system rejects the face-to-face availability (`GUIDANCE_OFFICE_REQUIRED`) and nothing is saved; the Counselor must configure the location or correct the schedule before retrying. Active weekly periods may not overlap each other for the same Counselor. Valid schedules persist as recurring university-local (`Asia/Manila`) definitions. Counselors can disable and later enable a schedule; enabling repeats the overlap and location checks. Delete removes the definition from the Counselor's list and future slot generation while retaining its database row and existing appointment references. Adding the exact same definition later reuses the retained row.

**2. Counselor blocks unavailable time.** Instead of changing the weekly schedule, a Counselor creates a temporary block: a date or datetime range, optionally whole-day, with an optional short reason (≤ 255 characters). The system rejects a block that would overlap an existing `PENDING` or `CONFIRMED` appointment (`BLOCK_CONFLICT`) — the affected appointment must be resolved first; a block never cancels, rejects, reschedules, or moves an appointment. Valid blocks save without touching the recurring schedule. When generating and calculating bookable slots, the system excludes blocked periods, existing appointments, and past times. Weekly-schedule changes apply to future availability. Matching future `AVAILABLE` slots adopt the active schedule's supported mode when availability is materialized; leftover available slots attached to the replaced, inactive schedule are excluded from calendars and booking. `RESERVED` slots and existing appointments remain unchanged.

**3. Student selects an appointment.** An `ACTIVE` Student searches future available slots. The system displays each slot's campus, date, time, supported modes, and Guidance Office location. Beside the calendar, beneath the selected campus, the Student selects one or more concern checkboxes: Family, Financial, Academic, Relationship, and Custom. The first selected concern is the priority; remaining concerns retain selection order, and removing the priority promotes the next selected concern. **All of the above** is a shortcut that selects the four standard topics in display order after existing selections; it is checked when all four are selected, and unchecking it clears those four. Custom requires a short description; optional details may accompany other selections. New bookings require at least one category, and details are limited to 500 characters. The selected ordered categories and details remain attached to the appointment when rescheduled. They are visible only to the Student and assigned Counselor in appointment requests, appointment details, and session details, separate from the Counselor-authored assessment. Concern data must not appear in generic reminders, notifications, call/chat payloads, audit content, or ordinary logs.

**4. System validates the request.** The system re-checks that the slot is still available, the mode is supported, and no participant conflict exists. A slot whose Manila date has already passed is rejected with `APPOINTMENT_DATE_PASSED`; a slot whose start time has already passed today is rejected with `APPOINTMENT_TIME_PASSED` (both 409, original reservation untouched on reschedule). Other failures inform the Student the selection is unavailable or incompatible (`SLOT_UNAVAILABLE`, `MODE_INCOMPATIBLE`, `SCHEDULE_CONFLICT`, `GUIDANCE_OFFICE_REQUIRED`) and returns to the available slots. On success the system atomically reserves the slot and creates a `PENDING` appointment. `ONLINE` keeps `meeting_location` empty; `FACE_TO_FACE` copies the current campus Guidance Office location into `appointments.meeting_location` as a booking-time snapshot — later campus-location edits do not alter the existing appointment.

**5. Counselor reviews the request.** The assigned Counselor reviews the request, schedule, and mode. Rejection sets `REJECTED`, optionally with a note (≤ 500 characters), and releases the slot; the Student may then choose another slot or mode. Approval sets `CONFIRMED` (denied after the scheduled start).

**6. Actions after confirmation.** Cancellation sets `CANCELLED` and releases the future slot. Students may cancel or reschedule only until 24 hours before start; the assigned Counselor is unrestricted by that cutoff. Rescheduling (`CONFIRMED` only) selects a replacement slot and supported mode, returns the appointment to `PENDING`, and replaces the location snapshot atomically. Any participant join/message activity prevents rescheduling. Before start and before chat activity, the assigned Counselor may change to another mode supported by the same slot while keeping the appointment `CONFIRMED`. A failed change leaves the original reservation intact.

**7. Online appointment.** The appointment lobby opens 30 minutes before start. At the scheduled start, the system authorizes the owning Student and assigned Counselor for the dedicated appointment text chat and the one-to-one WebRTC audio/video call under `AUDIO_VIDEO_CALLS.md`. An open scheduled-session page submits the authorized text-chat join automatically at/after start; the request is still required, does not renew idle activity, and a failed attempt offers a manual retry. Joining either channel is independent; both authorize the same appointment participants, confirmed `ONLINE` status, and session window.

**8. Face-to-face appointment.** The system displays the saved campus Guidance Office location snapshot, and the Student attends onsite at that location.

**9. Session outcome and documentation.** After either mode, only the assigned Counselor records the appointment outcome after start; face-to-face outcomes are entered manually. `COMPLETED` means the session occurred and `NO_SHOW` means the Student did not attend. On the scheduled session page, the header's **Mark as done** (beside **Mark no-show**) finalizes a complete assessment and completes the appointment in one transaction; Counselor History keeps the status-only **Mark completed**, and the standalone record page keeps **Finalize record**. The counseling-session record otherwise follows `COUNSELING_SESSION_RECORDS.md`. Ending a chat/call does not by itself invent an appointment outcome.

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

The authenticated `#appointments` screen presents a month calendar with previous/next navigation and a month/year picker. Student booking is a guided six-stage flow: choose Counselor, date, time, session mode, review, and submit. Counselor choices come from `GET /booking-counselors`, which returns only active counselor IDs and display names; the Student calendar and slot search are scoped to that Counselor. The selected concrete slot ID and mode still go through the existing appointment create/reschedule API, where availability, mode compatibility, conflicts, and location are revalidated. The modal preserves choices when navigating backward and clears date/time/mode when Counselor or date changes. It distinguishes loading, empty availability, refresh failures, and stale slots. The Counselor appointment view retains its own calendar behavior.

Users can navigate across months and years; the frontend requests one complete month at a time through `GET /calendar`, keeping every request within the endpoint's 63-day maximum. Past months remain visible for reference but past dates cannot be selected. Viewing a future month does not imply availability: only dates with actual future slots are bookable. `GET /calendar` materializes concrete slots from active weekly schedules for the requested range, then returns calendar-date metadata, blocked dates, and generated slot availability, identified by `Asia/Manila`; blocked-period exclusion happens at slot generation. Each day carries `is_past`; `available_times` contains sorted, distinct Manila start times and `available_slots` contains sorted, distinct Manila start/end intervals from actual future `AVAILABLE` slots, excluding temporary time blocks and each owning Counselor's whole-day blocks. Counselor calendar responses also contain only the owner's pending/confirmed `booked_slots` (time interval and status only); Students receive none. Counselor calendars use only their own slots; Student calendars use active Counselors, or the selected active Counselor when filtered. Duplicate intervals across Counselors appear once in an unfiltered calendar. Saturday and Sunday follow the same calendar selection rules as weekdays: past dates and explicitly blocked dates cannot be selected, while a date with no slots may be selected to show that no times are offered. Days with no slots return empty lists, never default availability placeholders. Fully past days return no available times, and today keeps only Manila times still ahead of now. On the Counselor calendar, selecting a date shows the owning Counselor's pending or confirmed booked intervals and status in a list below the calendar. The frontend drops already-started slots from the list between refreshes. Calendar interval labels also remove elapsed starts every second and on window focus, without making a request or renewing the session. Counselors use `POST /calendar/blocks` and `DELETE /calendar/blocks/{blocked_date}` for whole-day blocks. The frontend refreshes when the screen opens, after block changes, on month changes, and on date changes, plus a background refresh every 60 seconds that does not extend an authenticated session; the appointment API remains the authoritative booking and conflict boundary.

## Implemented availability management endpoints

Weekly schedules and temporary blocks are fully implemented (`GET /weekly-schedules`, `POST /weekly-schedules`, `POST /weekly-schedules/standard-weekdays`, `POST /weekly-schedules/{weekly_schedule_id}/replace`, `DELETE /weekly-schedules/{weekly_schedule_id}`, `POST /weekly-schedules/{weekly_schedule_id}/enable`, `DELETE /weekly-schedules/{weekly_schedule_id}/remove`, `GET /availability-blocks`, `POST /availability-blocks`, `DELETE /availability-blocks/{availability_block_id}`), and the counselor appointments screen provides management forms for both: a recurring weekly schedule form (campus, day, local time range, slot duration, mode) and a temporary unavailable-time form with a list of existing blocks. The standard-weekday action creates or restores Monday–Friday 08:00–16:00 schedules as a validated batch; it rejects the entire operation if any day conflicts or the campus/mode is invalid, and leaves existing appointments unchanged. Schedule editing uses the atomic replacement endpoint: the previous active definition is deactivated only when the validated replacement is ready. Matching future unreserved slots adopt the replacement mode on materialization, while stale slots linked to inactive or deleted definitions no longer appear; reserved slots and existing appointments remain unchanged. The remaining scheduling endpoints are listed in `docs/API_CONTRACT.md`.

## V1 boundary

- Recurring weekly schedules with concrete slot materialization on demand; no appointment-history table.
- Availability generation may accept a time range and slot duration but persists concrete slots (`POST /availability-slots` still supports manual concrete batches of 1–200 slots).
- Status transitions and slot reservation/release must be atomic and auditable.
- Mode compatibility and face-to-face location availability are validated server-side.
- Legacy Guidance Staff and Superadmin have no appointment-participant or campus-schedule authority. Superadmin may see minimal operational metadata only.
- Scheduled online counseling retains CounselConnect text messaging and provides one-to-one WebRTC audio/video; no recording or transcript and no persisted call metadata.

## Required tests

- Available request and concurrent/double-book attempt.
- `ONLINE`, `FACE_TO_FACE`, and `BOTH` slot compatibility, including forbidden combinations.
- Face-to-face-capable availability denied when the campus Guidance Office location is missing.
- Correct face-to-face location snapshot and protection from later campus-location changes.
- Pending review and each allowed/forbidden appointment transition.
- Ownership and role access, including other-Counselor, legacy Guidance Staff, and Superadmin participant denial.
- Required nonempty concern selection, ordered priority semantics, All-of-the-above expansion, Custom detail validation, reschedule preservation, and concern confidentiality.
- Cancel/reschedule slot release and replacement-mode/location revalidation.
- Weekly-schedule constraint enforcement (day, time range, duration bounds, mode enum, overlap, exact duplicate, foreign keys).
- Availability-block overlap with active appointments denied; block deletion.
- Slot materialization from weekly schedules excludes blocked periods and duplicates.
- Online conversation denied before confirmation or scheduled start.
- An open session page submits the authorized join once at/after start for the current participant; an already-joined participant is not joined again, and a failed attempt exposes only a manual retry.
- Appointment/conversation Student and Counselor mismatch denial.
- Face-to-face conversation-link denial and one-conversation-per-appointment enforcement.
- Call denied before confirmation, outside the appointment window, for face-to-face appointments, and for non-participants.
- Call signaling relayed only between the two participants; duplicate/third connections and invalid/oversized signals closed.
- Call window ends on cancellation/outcome, and no call media/SDP/candidates/history are persisted.
- Separation of `GENERAL`, `APPOINTMENT`, and `SOS` conversations.
- Session-page header mark-as-done finalizes and completes atomically; missing/incomplete records and pre-start calls change nothing; History completion and no-show never finalize; a completed record can be reopened and re-finalized.
- UTC persistence and `Asia/Manila` display.

## Implemented scheduling flow

The scheduling UI is at `#appointments`, available from the signed-in navigation to active Students and Counselors. Student sign-in opens Student services with an appointment link. Legacy Guidance Staff, Superadmin-as-participant, and pending/expired Students cannot load appointment counseling data. The reference flow includes appointment concern, audio/video, and counseling-record finalization.

- Counselor sets recurring university-local availability through weekly schedules (day 1–7 ISO, campus, local time range, 15–240-minute slot duration, mode). Slots are materialized lazily from active schedules when a calendar/slot search needs them, skipping availability-blocked periods and already-materialized times; manual concrete batch creation remains available. Counselor availability cannot overlap across campuses.
- Students filter future slots by campus, Philippine date, and mode; requesting a slot creates `PENDING`. The owning Counselor can confirm or reject a pending request. Rejection optionally includes a note of at most 500 characters.
- Owner Student or assigned Counselor can cancel `PENDING` or `CONFIRMED`. They can reschedule `CONFIRMED` to a different future available slot; the same appointment returns to `PENDING` for review. A Counselor can select only their own replacement slots. A Student can select another Counselor. The replacement mode and campus location are revalidated and its location snapshot replaces the previous booking snapshot atomically. A linked online session prevents rescheduling.
- Only the assigned Counselor records `COMPLETED` or `NO_SHOW`, from `CONFIRMED` and once the scheduled start has been reached. Confirmation after the start is denied. Students cannot cancel or reschedule inside 24 hours of the scheduled start; Counselors retain the authorized action.
- The scheduled session page header's **Mark as done** saves the assessment, finalizes a draft (or accepts an already-final record), and completes the appointment atomically. It returns `409 RECORD_NOT_SAVED`, `409 RECORD_INCOMPLETE` with `details.fields`, or `409 SESSION_NOT_STARTED` without changing state. History **Mark completed** and **Mark no-show** remain status-only and never finalize the record. Reopening a finalized record is allowed for `CONFIRMED`/`COMPLETED` appointments and never re-locks files.
- User-row locks in ascending ID order serialize participant conflicts; subsequent appointment, ordered slot, and campus locks revalidate current state. The generated unique active-slot constraint remains the database backstop. Failed replacement requests leave the original reservation intact. Terminal transitions release the reservation; searches exclude past slots.
- Counselor may update a nonblank Guidance Office location. Existing face-to-face snapshots remain unchanged. Missing location blocks face-to-face-capable slot creation and face-to-face booking/rescheduling.
- Lists are scoped to the acting Student or assigned Counselor, paginated at 20 by default (maximum 100), and returned with `Cache-Control: no-store`. Both appointment screens provide status filters for `CONFIRMED`, `PENDING`, `COMPLETED`, `NO_SHOW`, `CANCELLED`, and `REJECTED`, so cancellation history remains visible to both participants and a Student can read the Counselor's rejection note. State changes use the existing cookie/CSRF controls and minimal audit events, with no confidential content copied into audit metadata.
- Dates persist in UTC and serialize with `Z`; form inputs and displays use `Asia/Manila`, independent of the browser's timezone. Refresh is explicit; the appointments screen additionally uses a background refresh interval that never renews session activity.

**Scheduled Live Chat boundary:** confirmed online appointments appear in an appointment-derived launcher. The lobby opens 30 minutes before start. Confirmation does not create a conversation; the open session page automatically submits the first authorized join at or after start, and that request still creates or reuses the single appointment conversation (a failed attempt offers a manual retry). REST persists and retrieves ordered messages, while WebSockets deliver committed events. At slot end plus the configured 15-minute grace period, the worker closes an open conversation with `TIMEOUT` without changing the `CONFIRMED` appointment outcome.

**UI boundary:** weekly-schedule and availability-block management forms are implemented on the counselor appointments screen, with backend audit events. The scheduled-session page provides lobby, automatic authorized join with manual retry, durable text messaging, reconnection catch-up, **Mark no-show**, and the header **Mark as done** (which finalizes the assessment and completes the session); the right-hand tab content scrolls inside its panel. Counselor History keeps **Mark completed**. Closed history is Counselor-only until retention cleanup.

Appointment records may be filtered by aware `starts_after` (inclusive) and `ends_before` (exclusive) query parameters on `GET /appointments`. The Counselor dashboard uses a Manila-local day converted to UTC boundaries, so its “today” list does not depend on the first page of all appointment history.

## Pending policy and integration

Slot duration/buffer defaults, detailed no-show policy, production video TURN service, and assessment/document retention. The 60-day booking horizon remains approved by ADR-021.

### Slot-list pagination

`GET /availability-slots` excludes counselor-owned whole-day blocks (using the slot start date in Asia/Manila) and overlapping temporary time blocks before counting and paginating. `total` counts all matching slots, including when the requested page is empty. A block belonging to one Counselor never excludes another Counselor's slots. Existing role scope, mode, campus, and date filters remain in effect.

When a Student chooses a Counselor and date, the frontend retrieves every page of that Counselor's slots for the date (the endpoint maximum is 100 per page). If that Counselor has multiple campus slots with the same displayed start time, the Student selects the campus before choosing a compatible mode and submitting the selected `availability_slot_id`. The server revalidates current availability and retains the final authority over booking conflicts.
