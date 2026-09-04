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

## Pending

Slot duration/buffer, cancellation/reschedule cutoff, blocked periods, reminders, detailed no-show policy, and any allowed pre-start join window.
