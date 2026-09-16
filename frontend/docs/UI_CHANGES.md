# UI Changes & Modularization

This document records the structural updates and role-based page separation under `frontend/src/`.

## Summary of Changes

1. **Student & Counselor Appointment Page Separation:**
   - Extracted student appointment management from `AppointmentsPage.jsx` into `frontend/src/pages/student/StudentAppointmentsPage.jsx`.
   - Extracted counselor appointment management and weekly availability editor from `AppointmentsPage.jsx` into `frontend/src/pages/counselor/CounselorAppointmentsPage.jsx`.
   - Retained `AppointmentsPage.jsx` as a thin compatibility wrapper.

2. **Student & Counselor Homepage & Dashboard Separation:**
   - Utilized dedicated role-based page components:
     - `frontend/src/pages/student/student_homepage.jsx`
     - `frontend/src/pages/counselor/counselor_dashboard.jsx`
   - Retained `HomePage.jsx` as a thin compatibility wrapper.

3. **Hash-Based Routing (`App.jsx`) Refactoring:**
   - Updated `src/App.jsx` to directly route `#home` and `#appointments` based on `session.user.role_code` (`STUDENT` vs `COUNSELOR`), preserving all existing hash routes (`#home`, `#appointments`, `#review`, etc.) and `window.location.hash`.

4. **Shared Components & Features:**
   - Reused shared components (`BookingModal.jsx`, `CalendarGrid.jsx`, `AppNavBar.jsx`) and hooks (`useAppointments`, `useSession`) without duplication.

5. **Testing & Build Verification:**
   - All 47 frontend tests pass successfully (`node --test frontend/tests/*.test.cjs`).
   - Production build compiles cleanly with Vite (`vite build`).

---

## Dependency Check & Compatibility Wrapper Report

A dependency check across `frontend/src/` and `frontend/tests/` revealed the following regarding `HomePage.jsx` and `AppointmentsPage.jsx`:

1. **Source Code Imports (`src/`):**
   - Neither `HomePage.jsx` nor `AppointmentsPage.jsx` is imported by any file in `src/`. `App.jsx` routes directly to the specialized role pages (`StudentHomePage`, `CounselorDashboard`, `StudentAppointmentsPage`, `CounselorAppointmentsPage`).

2. **Test Suite Imports (`tests/`):**
   - Both files are imported by test suites (`frontend/tests/live-appointments.cjs` and `frontend/tests/appointments.test.cjs`) as direct module entry points for mounting and testing role-based rendering.

3. **Routing Reachability:**
   - Neither wrapper file is reachable through the live application's hash routing (`App.jsx` bypasses them entirely).

4. **Deletion Safety:**
   - While changing or deleting them has zero effect on the live app's Student or Counselor UI, they **must remain as compatibility wrappers** because the test suite depends on them. Removing them would cause test failures unless tests are refactored to import the specialized page components directly.

---

## 2026-09-16 — Appointment regression investigation + Counselor CSS leak fix

Cross-checked the current structural refactor against the committed legacy (`HEAD` = `63aa98f` monolithic `AppointmentsPage.jsx` / `HomePage.jsx`) to locate the reported "appointments not working" break.

### Investigation result — appointment logic was NOT broken

The role split is faithful (read-only verification; no appointment data wiring removed):

- Normalized (comment/encoding-mojibake-stripped) diff of `HEAD:…/AppointmentsPage.jsx` vs the combined `student/StudentAppointmentsPage.jsx` + `counselor/CounselorAppointmentsPage.jsx` shows only import-path moves, `RecordsTabs({ state })` dropping the already-unused `counselor` arg, and typographic repairs (`…`, `·`, `—`).
- `recordsLoading` / `recordsError` (student + counselor records views) and `availabilityBlocksLoading` / `availabilityBlocksError` are preserved.
- Dev-server `GET` of `App.jsx`, `HomePage.jsx`, `AppointmentsPage.jsx`, `student/student_homepage.jsx`, `student/StudentAppointmentsPage.jsx`, `counselor/counselor_dashboard.jsx`, `counselor/CounselorAppointmentsPage.jsx` → all HTTP 200 (no compile/transform error).

### Operational cause (git tracking — not a frontend edit)

- `frontend/src/pages/{student,counselor}/` are **untracked** (`??`). After the refactor, `AppointmentsPage.jsx` / `HomePage.jsx` were reduced to thin import wrappers. A `git clean -fd` or `git stash` (without `-u`) deletes the untracked split files, so the wrappers' imports resolve to nothing → crash. Fix is `git add frontend/src/pages/{student,counselor}` (repo-tracking decision on the user/merge side).

### Boundary violation introduced & fixed: shared `.home-page` CSS

- The earlier "cover the whole screen" `bg-tint` task placed centering on the **base `.home-page`** class. That class is shared with the **Counselor` side: `counselor/counselor_dashboard.jsx` → `<main className="home-page">` (and `<section class="dashboard-hero">`), so the student-only flex/centering/min-height was leaking into Counselor visuals — against the "Student side only / Counselor unchanged" boundary.
- **Fix (1 file, `frontend/src/index.css`)**: base `.home-page` reverted to the legacy neutral `background: #ffffff` (no flex/centering) → Counselor dashboard visually identical to `HEAD`. Student-only geometry (`min-height: calc(100vh - 73px); display:flex; flex-direction:column; align-items:center; justify-content:center;`) moved onto the scoped selector `.home-page.bg-tint`; the student `<main>` already carries the Tailwind `bg-tint` utility so Counselor (no `bg-tint`) is unaffected. Tint colour unchanged (`#eff6ff`, Tailwind utility).

### Files changed this task

- `frontend/src/index.css` — revert base `.home-page` to `#ffffff`; add scoped `.home-page.bg-tint` block. No component, hook, route, or API change.
- `frontend/docs/UI_CHANGES.md` — this log entry (appended).

### Data contract fields touched

- None (styling and investigation only). No route, hook, prop, fetch path, request/response field, or a CSS class name consumed by `frontend/tests/**` was renamed.

### Verification

- `node --test frontend/tests/*.test.cjs` — 47/47 pass.
- `node node_modules/vite/bin/vite.js build` — clean compile.
- Module-transform probe on the Vite dev server (HTTP 200) for `App.jsx`, both wrappers, and both role-split appointment/home pages.

### Rollback

```bash
git checkout HEAD -- frontend/src/index.css
```
Restores base `.home-page` to legacy `#ffffff` (reverts both the leak-fix and the student geometry); no component/data-flow change is rolled back.

### Boundary preserved

- Student-only: no Counselor/Guidance Staff component, sidebar, route, review console, selector, or class name changed (the only action taken was undoing a previous cross-role leak). No hash-route change (`#home` unchanged), no endpoint change, no component or CSS selector removed/renamed (pure additive/return-to-legacy selector scoping).
