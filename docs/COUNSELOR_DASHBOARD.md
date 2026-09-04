# CounselConnect — Counselor and Guidance Staff Dashboards

Dashboard visibility never replaces backend authorization.

## Guidance Staff dashboard

Only assigned enrollment-verification queue, Student/academic details needed for that decision, temporary current COR access, and `APPROVED` / `NEEDS_RESUBMISSION` / `REJECTED` actions.

## Counselor dashboard

- all authorized COR verification,
- Counselor-only campus Guidance Office location configuration,
- concrete availability with `ONLINE`, `FACE_TO_FACE`, or `BOTH` support,
- appointment requests, selected modes, schedules, location snapshots, and outcomes,
- authorized `GENERAL`, `APPOINTMENT`, and `SOS` conversations,
- resource review/manual resources/categories/publication,
- CMS, FAQs, announcements, and emergency contacts,
- authorized user/Guidance Staff account management,
- permitted Student academic corrections,
- minimal authorized operational/audit activity.

For face-to-face-capable availability, the dashboard must require a configured Guidance Office location for the selected campus. Changing the campus location affects future bookings only; existing appointments retain their stored `meeting_location` snapshot.

Counselor is the highest-authority role but access remains purpose-bound; audit/activity views should not expose unnecessary counseling content.

## Required tests

Staff assignment isolation; Staff denial for every Counselor-only module; Counselor module authorization; Counselor-only campus-location mutation; missing-location face-to-face availability denial; existing appointment location-snapshot stability; mode-aware appointment queues; appointment-conversation participant authorization; COR cleanup; sensitive content omitted from audit views; user/role/academic/content actions audited.
