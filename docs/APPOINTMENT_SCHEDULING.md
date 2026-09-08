# CounselConnect — Appointment Scheduling

## Contract

Counselor creates concrete campus/date/time slots and assigns each slot a `delivery_mode`: `ONLINE`, `FACE_TO_FACE`, or `BOTH`. An `ACTIVE` Student requests one available slot and selects an `appointment_mode` of `ONLINE` or `FACE_TO_FACE` that the slot supports. The system atomically prevents conflicts, reserves the slot, and creates a `PENDING` appointment. Counselor sets `CONFIRMED` or `REJECTED`.

Counselor alone configures `campuses.guidance_office_location`. A campus without a configured Guidance Office location cannot offer `FACE_TO_FACE` or `BOTH` availability. For a face-to-face request, the system copies the current campus location into `appointments.meeting_location` as a booking-time snapshot; later campus-location edits do not alter the existing appointment.

Final outcomes are `COMPLETED`, `CANCELLED`, and `NO_SHOW`. Rescheduling must revalidate the replacement slot, selected mode, and campus location. Only the owner Student and authorized Counselor may access or update an appointment.

## Online appointment integration

- A confirmed `ONLINE` appointment may create or reuse exactly one dedicated conversation when the scheduled start is reached.
- The linked conversation uses `conversation_type = APPOINTMENT`.
- The appointment and conversation must contain the same Student and Counselor.
- `appointments.conversation_id` is nullable and unique.
- A `FACE_TO_FACE` appointment must not have an appointment-linked conversation.
- `GENERAL` Live Chat and `SOS` conversations remain separate from scheduled appointment conversations.
- Ending the online conversation returns control to the appointment workflow; only an authorized appointment outcome transition sets `COMPLETED` or `NO_SHOW`.

## V1 boundary

- Concrete slots only; no recurrence engine or appointment-history table.
- Availability generation may accept a time range and slot duration but persists concrete slots.
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
- Online conversation denied before confirmation or scheduled start.
- Appointment/conversation Student and Counselor mismatch denial.
- Face-to-face conversation-link denial and one-conversation-per-appointment enforcement.
- Separation of `GENERAL`, `APPOINTMENT`, and `SOS` conversations.
- UTC persistence and `Asia/Manila` display.

## Implemented scheduling flow

The scheduling UI is at `#appointments`, available from the signed-in navigation to active Students and Counselors. Student sign-in opens Student services with an appointment link. Guidance Staff and pending/expired Students cannot load appointment data. The reference is **Flowchart V1, page 4 (Appointment Scheduling)**.

- Counselor selects a campus, time range, duration, and supported mode; the API persists concrete slots. A range must contain whole slots, with a technical batch maximum of 200. No duration/buffer policy or recurrence is assumed. Counselor availability cannot overlap across campuses.
- Students filter future slots by campus, Philippine date, and mode; requesting a slot creates `PENDING`. The owning Counselor can confirm or reject a pending request. Rejection optionally includes a note of at most 500 characters.
- Owner Student or assigned Counselor can cancel `PENDING` or `CONFIRMED`. They can reschedule `CONFIRMED` to a different future available slot; the same appointment returns to `PENDING` for review. A Counselor can select only their own replacement slots. A Student can select another Counselor. The replacement mode and campus location are revalidated and its location snapshot replaces the previous booking snapshot atomically. A linked online session prevents rescheduling.
- Only the assigned Counselor records `COMPLETED` or `NO_SHOW`, from `CONFIRMED` and once the scheduled start has been reached. Confirmation after the start is denied. No additional no-show threshold or cancellation/reschedule cutoff has been chosen.
- User-row locks in ascending ID order serialize participant conflicts; subsequent appointment, ordered slot, and campus locks revalidate current state. The generated unique active-slot constraint remains the database backstop. Failed replacement requests leave the original reservation intact. Terminal transitions release the reservation; searches exclude past slots.
- Counselor may update a nonblank Guidance Office location. Existing face-to-face snapshots remain unchanged. Missing location blocks face-to-face-capable slot creation and face-to-face booking/rescheduling.
- Lists are scoped to the acting Student or assigned Counselor, paginated at 20 by default (maximum 100), and returned with `Cache-Control: no-store`. State changes use the existing cookie/CSRF controls and minimal audit events, with no confidential content copied into audit metadata.
- Dates persist in UTC and serialize with `Z`; form inputs and displays use `Asia/Manila`, independent of the browser's timezone. Refresh is explicit and there is no scheduling background poll.

**Integration boundary:** online slots and requests are supported, but scheduled Live Chat joining/message exchange is not implemented. The UI states this before booking and on confirmed online appointments. The existing messaging service now validates participant/mode/type linkage and closes an already-linked conversation when an authorized terminal outcome occurs. It does not create or open conversations. The online integration requirements above remain requirements for the separate Live Chat implementation.

## Pending policy and integration

Slot duration/buffer, cancellation/reschedule cutoff, blocked periods, reminders, detailed no-show policy, and any allowed pre-start join window.
