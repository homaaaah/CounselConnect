# CounselConnect — Roles and Access

Backend checks are authoritative. Counselor is the highest-authority role for counseling operations. A narrow `SUPERADMIN` recovery role exists (ADR-030); it has no COR-approval or counseling authority, but it does ratify Student-initiated profile-edit requests during verification (ADR-032).

Sign-in entries: Students use `#login`, Counselors/Guidance Staff use `#staff-login`, and Superadmins use the separate `#superadmin-login` page or landing-modal entry. Frontend audience checks revoke mismatched fresh sessions through the existing logout flow; they do not replace backend resource authorization. There is no public Superadmin registration entry.

| Capability | Student | Guidance Staff | Counselor |
|---|:---:|:---:|:---:|
| Register/upload current COR | Own | — | — |
| COR verification | Automated screening + own confirmation (ADR-029) | — | Read-only screening records |
| Read registration correction status | Own session/account only (Task 4.5) | ? | ? |
| View student directory | Own account | — | Read-only users list with screening status |
| Use normal Student services | Own, while `ACTIVE` | — | — |
| Availability/appointments | Request/manage own; select compatible mode; join own confirmed online session | — | Manage slots, modes, decisions, outcomes, and campus Guidance Office locations |
| Messaging/SOS | Own authorized interactions | — | Authorized interactions |
| Facial observation | Allow/decline the local session; sees sharing status and Stop only | — | Request/finish/stop; the only role that sees the temporary timeline and summary |
| Review/manage resources | View published | — | Manage |
| Assistant | Use | — | Manage source content through CMS/resources |
| CMS/FAQ/announcements/contacts | View published | — | Manage |
| Future authorized account/Guidance Staff operations (outside this module) | — | — | Manage authorized records |
| Operational audit | — | — | Authorized view |

## Boundaries

**Implemented backend and frontend:** [Registration Information Corrections and Users Management](REGISTRATION_CORRECTIONS.md) governs Superadmin Users operations and registration-correction detail/evidence/return/resubmission. Only active, non-deactivated Superadmins review corrections; Students read only their own versions. Counselor/Guidance Staff cannot review them. Operational deactivation is independent of enrollment and correction status; Superadmin/Guidance Staff status changes are excluded.

- Every role uses a one-hour idle and 12-hour absolute authenticated-session limit with a five-minute warning. Genuine CounselConnect actions renew idle activity; background polling and WebSocket heartbeats do not. `Remember Me` is unavailable in v1.
- Counselor SOS presence is separate from authentication: explicit `AVAILABLE`, `BUSY`, or `UNAVAILABLE` plus a valid connection and recent confirmation. Logout, session expiry, or lost connection makes the Counselor unavailable.
- Pending/expired Students may access only account and COR re-verification functions.
- Guidance Staff is not a junior Counselor: no appointments, messaging, SOS, resources, CMS, user management, campus Guidance Office location configuration, or audit access unless a future approved decision expands the role. COR verification is automated (ADR-029); Guidance Staff holds no COR duty.
- Only Counselor may configure `campuses.guidance_office_location` and create `ONLINE`, `FACE_TO_FACE`, or `BOTH` availability.
- Students may select only a mode supported by the slot and may access only their own confirmed online appointment conversation at the authorized time.
- Counselor authority still follows assignment, purpose, and least privilege; it is not permission to browse unrelated confidential content.
- Initial staff accounts may be developer-created. User-approved 2026-10-26 scope (ADR-035) also permits active non-deactivated Superadmins to create Counselor accounts with a Superadmin-entered initial password and edit only Counselor names/email. Server fixes the new role/status, email edits revoke sessions and stale edits are rejected. Guidance Staff/other-role provisioning, password reset/automatic delivery and role reassignment remain outside this module; clinical authority and assignment rules are unchanged. See the Users contract in `REGISTRATION_CORRECTIONS.md`.
- Superadmin (ADR-030) signs in with email, may read the student directory, and may reset a non-active Student to `PENDING_VERIFICATION` for a fresh COR (`POST /accounts/students/{user_id}/recover`). It must not declare a COR authentic or approve a registration, or access appointments, messaging, SOS, CMS, or audit content.
- Superadmin also reviews Student **profile-edit requests** made during verification (ADR-032): `GET /profile-change-requests` and `POST /profile-change-requests/{change_request_id}/approve|reject` (reject reason required). The Student's own submission activates the account with the COR-verified values; the Superadmin only ratifies the requested names/year_level/section. This is not registration or COR approval, and only editable fields can be requested (never student number, academic year, campus, or program).
- Task 4.5: Students may read only their own correction list/status details through `/profile-change-requests` using a session. Backend owner filtering/concealed 404 and a separate safe response omit reviewer IDs, COR metadata and clinical content. Pending/expired Students retain restricted feature access; deactivated Students cannot use these reads. Counselors/Guidance Staff cannot access the correction resource; Superadmin retains its existing queue permission, with full detail/private evidence still pending Task 5. No general audit browsing or correction decision permission is granted to Students.
- Students may sign in with their registered email or their student number (ADR-030); staff use email.
- A `PENDING_VERIFICATION` Student may cancel their own registration (`POST /cor-screenings/reject-account`, ADR-033): the account, screenings, COR files, sessions, profile, and pending edit requests are deleted and the email/student number are freed. Other statuses (including previously active accounts) cannot self-cancel. A technical screening failure creates no account at all.
