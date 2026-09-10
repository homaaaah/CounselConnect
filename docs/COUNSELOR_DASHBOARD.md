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

## Counselor SOS availability and background alerts

Counselor explicitly uses `AVAILABLE`, `BUSY`, or `UNAVAILABLE`; this presence is separate from authentication. SOS routing must also consider a valid authenticated connection and recent confirmation. A background tab may produce a browser notification, tab badge, or permitted sound, but notification content must remain generic and omit Student identity, answers, and case details. Logout, session expiry, or lost connection makes that Counselor unavailable. Exact response/fallback timing remains pending.

All dashboard roles use the approved one-hour idle and 12-hour absolute session limits. Warn five minutes before idle expiry and require explicit continuation or genuine CounselConnect activity; automatic heartbeats do not renew authentication.

For face-to-face-capable availability, the dashboard must require a configured Guidance Office location for the selected campus. Changing the campus location affects future bookings only; existing appointments retain their stored `meeting_location` snapshot.

Counselor is the highest-authority role but access remains purpose-bound; audit/activity views should not expose unnecessary counseling content.

## Required tests

Idle/absolute expiry for all roles; five-minute continuation; heartbeat non-renewal; `AVAILABLE`/`BUSY`/`UNAVAILABLE` behavior; generic background notification; unavailable-on-logout/expiry/disconnect; Staff assignment isolation; Staff denial for every Counselor-only module; Counselor module authorization; Counselor-only campus-location mutation; missing-location face-to-face availability denial; existing appointment location-snapshot stability; mode-aware appointment queues; appointment-conversation participant authorization; COR cleanup; sensitive content omitted from audit views; user/role/academic/content actions audited.
