# CounselConnect — Roles and Access

Backend checks are authoritative. Counselor is the highest-authority role; there is no Administrator role.

| Capability | Student | Guidance Staff | Counselor |
|---|:---:|:---:|:---:|
| Register/upload current COR | Own | — | — |
| Review COR verification | — | Assigned cases | All authorized cases |
| Use normal Student services | Own, while `ACTIVE` | — | — |
| Availability/appointments | Request/manage own; select compatible mode; join own confirmed online session | — | Manage slots, modes, decisions, outcomes, and campus Guidance Office locations |
| Messaging/SOS | Own authorized interactions | — | Authorized interactions |
| View session expression cue | Own status only | — | Read-only in active authorized interaction |
| Review/manage resources | View published | — | Manage |
| Assistant | Use | — | Manage source content through CMS/resources |
| CMS/FAQ/announcements/contacts | View published | — | Manage |
| Accounts/Guidance Staff/academic correction | — | — | Manage authorized records |
| Operational audit | — | — | Authorized view |

## Boundaries

- Every role uses a one-hour idle and 12-hour absolute authenticated-session limit with a five-minute warning. Genuine CounselConnect actions renew idle activity; background polling and WebSocket heartbeats do not. `Remember Me` is unavailable in v1.
- Counselor SOS presence is separate from authentication: explicit `AVAILABLE`, `BUSY`, or `UNAVAILABLE` plus a valid connection and recent confirmation. Logout, session expiry, or lost connection makes the Counselor unavailable.
- Pending/expired Students may access only account and COR re-verification functions.
- Guidance Staff is not a junior Counselor: no appointments, messaging, SOS, resources, CMS, user management, campus Guidance Office location configuration, or audit access unless a future approved decision expands the role.
- Only Counselor may configure `campuses.guidance_office_location` and create `ONLINE`, `FACE_TO_FACE`, or `BOTH` availability.
- Students may select only a mode supported by the slot and may access only their own confirmed online appointment conversation at the authorized time.
- Counselor authority still follows assignment, purpose, and least privilege; it is not permission to browse unrelated confidential content.
- Initial staff accounts are developer-created. Counselor may later manage authorized accounts and Guidance Staff.
