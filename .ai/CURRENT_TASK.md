# CounselConnect — Current Task

**Status:** ACTIVE
**Risk class:** MEDIUM (frontend integration; no backend/schema/auth changes)
**Task:** Apply the homaaaah capstone frontend (landing/home/login/register redesign, design CSS, auth modals) onto our project while keeping our newer appointments frontend (weekly-schedule/block UI, role-aware hook, live tests).

## Approach

1. Branch `frontend/capstone-landing-port` from `origin/main` (which already merged the recurring-schedules PRs).
2. Copy from the homaaaah snapshot: `LandingPage.tsx`, `HomePage.tsx`, `LoginPage.tsx`, `RegisterPage.tsx`, `index.css`, `App.tsx`, `index.html`, `landing-api.js`/public assets if present.
3. Keep OURS where ours is newer: `AppointmentsPage.tsx` (weekly-schedule/block sections), `useAppointments.ts` (role-aware), appointments feature index, `tests/appointments.test.cjs`, `tests/live-appointments.cjs`.
4. Reconcile `App.tsx` wiring (snapshot expects `onSignedIn` landing props); keep `LandingLink` if both use it.
5. Verify: `npm run build`, `npm test` (16 incl. session LoginPage markup assertions), backend live test, visual sanity via test renderer.

## Acceptance criteria

- Capstone landing/home design renders with real backend wiring (login/register modals call the API).
- Appointments screen keeps weekly-schedule/block management.
- All frontend tests + build pass; backend suite unaffected (no backend files touched).

## Out of scope

Backend, migrations, docs, root CHANGELOG.md, `.kilo/plans` (snapshot meta — skip to keep frontend-branch scope clean).
