# Port CCFrontend visual design into `frontend/`

**Status:** READY FOR IMPLEMENTATION
**Risk:** MEDIUM (presentation + navigation structure; no backend/schema change)
**Source:** `CCFrontend/frontend/` (forest-green variant)
**Target:** `frontend/` (currently the blue/Consolidated design)

## Goal

Apply CCFrontend's visual design — green landing/auth/booking surfaces and its page layouts — while keeping this repo's current behavior, hooks, backend contract, and data flows. Do **not** replace the whole frontend.

## Decisions

1. Design-only port, including page layouts (not a full mirror).
2. Keep current `useRegistration.js` (VALIDATION_ERROR messaging), `RegisterPage.jsx` (`status`/`alert` roles), notifications, `apiClient`, and all backend/docs code.
3. Adopt CCFrontend's top-bar navigation and remove the current counselor sidebar offset.
4. Green accents come from CCFrontend's CSS; `tailwind.config.js` stays unchanged (CCFrontend's is identical).
5. `CCFrontend/` remains untouched.

## Pre-checks

1. Confirm `CCFrontend/frontend/package.json` and `package-lock.json` match the repo's; if not, stop and report dependency differences.
2. Confirm the endpoints used by ported CCFrontend files exist in the current backend (already verified: `/accounts/register/student-with-cor`, `/cor-screenings/*`, `/profile-change-requests`, `/accounts/students`, `/appointments*`, `/conversations/*`, `/content/*`, `/auth/*`).
3. Record a clean baseline: `npm test` (currently 75 pass / 1 known calendar failure) and `npm run build`.

## Port list

### CSS and wiring
1. Replace `frontend/src/index.css` with `CCFrontend/frontend/src/index.css` (483 lines; green `--counseling-primary: #1C6B1B`; no landing/modal blocks).
2. Add `frontend/src/modal.css` from CCFrontend (790 lines; auth modal + booking-modal design).
3. Add `frontend/src/pages/LandingPage.css` from CCFrontend (663 lines).
4. `frontend/src/main.jsx`: add `import "./modal.css";` after `import "./index.css";`.
5. `frontend/src/pages/LandingPage.jsx`: add `import "./LandingPage.css";`; port CCFrontend's markup differences if the JSX differs (CCFrontend 340 lines vs repo 329).
6. Add `--primary: #4A6B5B` to the `:root` block so CCFrontend's `.btn-submit.btn-success { background: var(--primary) }` is explicit and keeps the same forest-green base. Do not otherwise alter CCFrontend CSS.

### Page layouts (CCFrontend versions)
Port these files, then reconcile behavior with the current tests:
- `src/App.jsx` (top-bar shell; drop `lg:ml-64`; CCFrontend handles landing section hashes)
- `src/components/layout/AppNavBar.jsx` (top bar instead of sidebar)
- `src/pages/student/student_homepage.jsx` (green bento layout)
- `src/pages/counselor/counselor_dashboard.jsx` (green metrics/chart layout)
- `src/features/counselor/useCounselorDashboard.js` (new) and `src/features/counselor/index.js` (export it)
- `src/components/appointments/BookingModal.jsx` (two-panel redesigned modal)
- `src/components/appointments/CalendarGrid.jsx` (modal variant)
- `src/pages/student/StudentAppointmentsPage.jsx` (CCFrontend layout)

Verify and skip files that are already identical (line counts suggest `CounselorUsersPage.jsx`, `CounselorAppointmentsPage.jsx`, `LoginPage.jsx`, `RegistrationStatusPage.jsx`, `components/appointments/ui.js` are identical or near-identical).

### Explicitly keep current versions
- `src/pages/RegisterPage.jsx` (current 490-line version with `role={result.success ? "status" : "alert"}`)
- `src/features/accounts/useRegistration.js` (VALIDATION_ERROR mapping)
- `src/features/appointments/useAppointments.js` (same public API; current behavior/tests)
- `src/components/feedback/Notifications.jsx` (current accessibility behavior)
- `src/services/apiClient.js`, all other feature hooks
- Backend, docs, migrations, OpenAPI

## Test reconciliation

1. Port CCFrontend's `tests/navbar.test.cjs` expectations for the top-bar layout, then re-add any current-only assertions that still hold.
2. Update only assertions made obsolete by the intentional design change:
   - sidebar-specific nav assertions
   - old student-home hero copy/buttons if the bento layout changes them
   - booking modal/calendar selectors only if labels/ids intentionally changed
3. Do not weaken tests for validation messaging, session safety, authorization, or API payloads.

## Validation

- `npm test` — expect all current tests to pass except the known pre-existing calendar date-rot failure unless the port fixes it.
- `npm run build` — must succeed.
- Manual checks:
  - Landing page: forest-green header/buttons/footer, `LandingPage.css` loaded.
  - Auth and booking modals: white card, forest-green primary buttons, two-panel booking layout.
  - Student home: green bento layout; booking flow still posts the same payload.
  - Counselor dashboard: green banner/metrics; data comes from existing endpoints.
  - Navigation: top bar, no sidebar overlap/offset.
- Confirm no backend/API/OpenAPI changes (`git status` should show only `frontend/` plus task/plan files).

## Risks

- **Navigation redesign** removes the fixed sidebar; layouts relying on `lg:ml-64` must be removed together with it.
- **CSS split** means removing landing/modal rules from `index.css` while adding the two new files; a missed import leaves pages unstyled.
- **Test churn**: some current tests assert the old sidebar/bento copy; update only those, preserving safety/API assertions.
- **CCFrontend `--primary`** was undefined; the explicit `#4A6B5B` keeps the current fallback look without changing the design.
- **Known calendar failure** is pre-existing; do not mask it as a new regression.

## Out of scope

- Backend, schema, migrations, OpenAPI, or auth behavior.
- Full CCFrontend mirror (hooks/tests/App internals beyond the listed files).
- Changing `tailwind.config.js` colors.
- Deleting or modifying `CCFrontend/`.
