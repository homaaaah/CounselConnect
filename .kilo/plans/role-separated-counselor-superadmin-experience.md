# Role-separated Counselor and Superadmin experience

**Status: Proposed implementation plan.** The existing role and access boundaries remain authoritative. This plan does not approve new permissions or change backend policy.

## Goal

Make the Counselor and Superadmin experiences visibly distinct and ensure Students cannot render or use Counselor-only or Superadmin-only pages by navigating directly to a hash route. Remove the Guidance sign-in switch from the Student login modal.

In this plan, **Counselor** means the `COUNSELOR` role (the Guidance Counselor). `GUIDANCE_STAFF` remains a separate, narrow role; it must not inherit Counselor or Superadmin pages.

## Current implementation

- `AppNavBar` already supplies different links for Students, Counselors, Superadmins, and Guidance Staff.
- `App.jsx` dispatches several pages by role: Counselor dashboard/schedule/history, Superadmin users/corrections, and Student services.
- The public landing login modal offered a Student a direct **Guidance sign in** switch. That switch has now been removed from the Student modal. The dedicated `#staff-login` page and its Student sign-in switch remain available; this is only an entry point, not authorization.
- Route visibility is not the security boundary. Protected API handlers must continue to enforce role, account state, ownership, and Counselor assignment independently.

## Target access map

| Role | Intended signed-in area | Explicitly excluded |
|---|---|---|
| `STUDENT` | Student home, own appointments/sessions, own registration status | Counselor schedule/history/dashboard; Superadmin users, corrections, and recovery |
| `COUNSELOR` | Counselor dashboard, assigned appointment operations, own schedule and history | Superadmin account recovery and registration-correction operations |
| `SUPERADMIN` | Account operations, Users, and the authorized registration-correction queue | Counseling operations, appointments, chats, SOS answers, assessments, clinical files, call media |
| `GUIDANCE_STAFF` | Existing narrow role only; landing behavior must be confirmed before redesign | Counselor features and all Superadmin operations |

## Implementation phases

### 1. Confirm route and capability inventory

- Inventory every current hash route, navigation entry, page component, and API request by role.
- Confirm that **Guidance Counselor** means `COUNSELOR`, not `GUIDANCE_STAFF`.
- Resolve the intended landing page for `GUIDANCE_STAFF`; do not default it to Student or Counselor content.
- Keep the role/capability matrix aligned with `docs/USER_ROLES.md` and the Superadmin limits in `docs/REGISTRATION_CORRECTIONS.md`.

### 2. Separate the signed-in page shells

- Keep one React application and shared authentication/session transport.
- Give Counselor and Superadmin distinct role-specific dashboard shells, page titles, and navigation groups. Reuse shared visual primitives where appropriate.
- Make the Counselor home lead to counseling operations. Make Superadmin home lead to account operations.
- Keep the Superadmin shell limited to Users and authorized registration corrections. Do not add counseling links or data.
- Keep Students on Student navigation and ensure there are no links to staff operations from Student pages.
- The Student login modal no longer links to Guidance sign-in. Keep the standalone staff sign-in route for staff who already know it, and keep the separate Superadmin entry as currently approved.

### 3. Enforce a route allowlist before rendering

- Centralize the frontend route-to-role map instead of relying on scattered fallback branches.
- On a role mismatch, do not mount the protected page or issue its data requests. Redirect to that role's own home or show a generic access-denied page.
- Preserve current active-account checks for Student/Counselor appointments and sessions.
- A guessed hash, stale browser history entry, or manually typed route must not expose another role's page.

### 4. Audit backend authorization without weakening contracts

- Verify each protected API route checks the exact allowed role and active/deactivated state.
- Verify owner and assigned-Counselor filtering for appointment, session, messaging, assessment, and clinical-document data.
- Verify Superadmin recovery/correction endpoints remain narrow and do not grant counseling or COR-authenticity authority.
- Add or repair backend authorization tests wherever the route audit finds a gap. Frontend guards alone are insufficient.

### 5. Verify role separation end to end

- Test the route matrix for Student, Counselor, Superadmin, and Guidance Staff, including direct navigation to every restricted hash.
- Assert restricted pages do not mount and their APIs are not called after a role mismatch.
- Exercise backend endpoints with wrong-role, inactive, deactivated, unassigned, and cross-owner identities.
- Check desktop/mobile navigation, modal close/switch behavior, page titles, browser back/forward, and session restoration.
- Run focused frontend and backend authorization tests, then the production frontend build and OpenAPI consistency check if API behavior changed.

## Acceptance criteria

- Students cannot view Counselor or Superadmin pages by clicking links or entering hashes directly.
- A Student login modal contains no Guidance sign-in link; a successful Student sign-in and registration path are unchanged.
- Counselors see only counseling operations and their assigned work.
- Superadmins see only authorized account operations and do not gain default access to counseling data.
- Guidance Staff remains distinct and does not inherit either privileged shell.
- Backend authorization remains authoritative for every protected operation.
- Existing role-mismatch login behavior, CSRF/session handling, and unrelated Student workflows continue to work.

## Not in scope

- Creating new roles, changing login credentials/audiences, or adding public Superadmin registration.
- Expanding Guidance Staff duties, Counselor authority, or Superadmin access.
- Replacing the modular monolith with separate applications or authentication systems.
- Changing database schema or API contracts unless the route audit proves a specific authorization gap that requires a separately reviewed change.
