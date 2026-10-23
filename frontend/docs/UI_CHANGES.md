# UI Changes & Modularization

> **Historical implementation log with revised target note (2026-09-20):** Entries below accurately describe the code at the time they were written. New frontend work must follow ADR-029–ADR-036: target roles are `STUDENT`, `COUNSELOR`, and `SUPERADMIN`; Guidance Staff/manual COR review and Wellness Resource UI are legacy; appointment concerns, scheduled audio/video, counseling records, clinical documents, and non-diagnostic AI observation are planned. Do not edit current screens as though those planned backend contracts already exist.

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
---

# CounselConnect Frontend Architecture & Restructuring Audit (Phases 1–4.1)

This document provides a comprehensive, end-to-end technical audit of all architectural updates, role-based page separations, responsive designs, reusable notification systems, CSRF hotfixes, and test/build verification performed across Phases 1 through 4.1 in `frontend/src/`.

---

## 1. Executive Summary

CounselConnect is a modular monolithic university counseling platform built with **React (JavaScript), Vite, TailwindCSS, FastAPI, and MySQL**. 
- **Routing:** Hash-based navigation via `window.location.hash` and `hashchange` listeners (no React Router).
- **Authentication & Security:** ADR-019 session-cookie auth with HttpOnly cookies for credentials and in-memory CSRF tokens (`X-CSRF-Token` header) for unsafe methods.
- **Roles:** `STUDENT`, `COUNSELOR`, `GUIDANCE_STAFF`.

Across Phases 1–4.1, the frontend underwent structured architectural refactoring to cleanly separate Student and Counselor pages, establish a reusable notification architecture, implement responsive styling on the Student homepage, and add robust CSRF auto-recovery—all while preserving 100% of existing functionality, backend API contracts, and passing all 47 test suites.

---

## 2. Phase 1 — Initial Baseline Audit

### Scope & Findings
- **Hash Navigation:** Inspected `src/App.jsx` and verified hash-based routing (`#landing`, `#login`, `#staff-login`, `#register`, `#home`, `#appointments`, `#review`).
- **Auth & Session:** Inspected `src/features/auth/useSession.js` and `src/services/apiClient.js`, confirming CSRF restoration via `GET /auth/csrf`.
- **Monolithic Dispatchers:** Identified that `HomePage.jsx` and `AppointmentsPage.jsx` acted as monolithic role dispatchers combining student and counselor logic.
- **Role Isolation:** Verified role boundaries (`STUDENT`, `COUNSELOR`, `GUIDANCE_STAFF`).

---

## 3. Phase 2 — Structural Refactoring (Page Separation)

### Architectural Goal
Break apart monolithic dispatchers into dedicated, clean page modules under `src/pages/student/` and `src/pages/counselor/`.

### Actions & Files Created/Modified
1. **Student Appointments (`src/pages/student/StudentAppointmentsPage.jsx`):**
   - Created new dedicated module containing student appointment records (Confirmed, Pending, Completed), pagination, appointment cards, cancel, and reschedule modal triggers.
2. **Counselor Appointments (`src/pages/counselor/CounselorAppointmentsPage.jsx`):**
   - Created new dedicated module containing student request reviews, Weekly Schedule Editor (replace/add weekly availability), Availability Calendar Grid, Date Blocking, and Temporary Unavailable Time Blocks.
3. **Student Homepage & Counselor Dashboard:**
   - Reused existing modules `src/pages/student/student_homepage.jsx` and `src/pages/counselor/counselor_dashboard.jsx`.
4. **App.jsx Routing (`src/App.jsx`):**
   - Refactored `src/App.jsx` to route `#home` and `#appointments` directly to the appropriate role-specific page components based on `session.user.role_code`.
5. **Compatibility Wrappers:**
   - Converted `HomePage.jsx` and `AppointmentsPage.jsx` into thin compatibility wrappers solely to ensure existing test suites (`live-appointments.cjs` and `appointments.test.cjs`) continue passing without breaking imports.

---

## 4. Phase 3 — Verification of Role Separation, Routing & Regression

- **Verification Scope:** Tested Student flows, Counselor flows, Guidance Staff flows, role boundaries, hash routing, authentication persistence, session restoration, and AppNavBar behavior.
- **Test Suite Results:** 47/47 tests passed successfully (`node --test frontend/tests/*.test.cjs`).
- **Production Build:** Clean compilation with Vite (`vite build`).

---

## 5. Phase 4 & 4.1 — Responsive Homepage & Reusable Notification Architecture

### 1. Responsive Student Homepage (`student_homepage.jsx`)
- Redesigned for Desktop, Tablet, and Mobile viewports with a centered card container (`max-w-2xl`), responsive typography (`text-2xl sm:text-3xl`), and flexible action button stacking on smaller screens.

### 2. Reusable Notification Architecture (`src/components/notifications/`)
- Extracted notification UI into decoupled, reusable components:
  - `NotificationBell.jsx`: Bell icon with an animated unread indicator dot (`•`).
  - `NotificationPanel.jsx`: Scrollable dropdown panel displaying role-specific notification cards with status icons (success/alert), message text, timestamps, and details.
- **Role-Aware Notification Sourcing (`AppNavBar.jsx`):**
  - **STUDENT:** Automatically fetches `/appointments` (for active students only) and maps `CONFIRMED` → "Appointment Accepted" and `REJECTED` → "Appointment Rejected" (with rejection notes).
  - **COUNSELOR:** Fetches `/appointments` and maps `PENDING` → "New Appointment Request".
  - **GUIDANCE_STAFF:** Fetches `/enrollment-verifications/pending` and maps pending verification cases → "New Review Request".
- **User-Specific Read/Unread Tracking:**
  - Stored in `localStorage` under a user-specific key: `cc_read_notifications_${user.user_id}` (preventing cross-user state leakage).

---

## 6. CSRF Auto-Recovery Hotfix (`src/services/apiClient.js`)

To prevent "request blocked: missing or invalid CSRF token" errors during appointment scheduling or state mutations when the in-memory CSRF token (`csrfToken`) is cleared or missing:
- Enhanced `request()` in `apiClient.js` to automatically check if `UNSAFE_METHODS` (`POST`, `PUT`, `PATCH`, `DELETE`) are executed while `csrfToken` is falsy.
- If missing, it transparently attempts to fetch `GET /auth/csrf` to recover the token from the HttpOnly session cookie before attaching it as `X-CSRF-Token`.
- **Safety Checks:** Explicitly excludes auth endpoints (`/auth/csrf`, `/auth/login`, `/auth/staff-login`, `/auth/logout`) to prevent infinite recursion, and fails cleanly if recovery fails.

---

## 7. Counselor Notification Real-Time Refresh Hotfix (`AppNavBar.jsx`)

To ensure Counselors instantly receive and display newly submitted student appointment requests (`PENDING`) without waiting up to 60 seconds or reloading the app:
- **Reactive Navigation Tracking:** Included `page` route changes in `useRoleNotifications()` dependency array so navigating across hash routes (`#home` ↔ `#appointments`) triggers an immediate notification fetch.
- **Window Focus Event Listener:** Added `window.addEventListener("focus", ...)` so switching back to the browser tab immediately refreshes notification data.
- **Responsive Polling Interval:** Shortened background polling from 60 seconds to **15 seconds** (`15_000ms`) for responsive, low-latency background updates.

---

## 8. Current Project Directory Structure (`frontend/src/`)

```text
src/
├── app/
│   ├── index.js
│   └── routes.js
├── assets/
│   ├── appointment.jpg
│   ├── bg.jpg
│   ├── communication.jpg
│   ├── counselor.jpg
│   └── library.jpg
├── components/
│   ├── appointments/
│   │   ├── BookingModal.jsx
│   │   ├── CalendarGrid.jsx
│   │   └── ui.js
│   ├── feedback/
│   │   └── index.js
│   ├── layout/
│   │   ├── AppNavBar.jsx
│   │   └── index.js
│   ├── notifications/
│   │   ├── NotificationBell.jsx
│   │   ├── NotificationPanel.jsx
│   │   └── index.js
│   └── ui/
│       └── index.js
├── features/
│   ├── accounts/
│   │   ├── index.js
│   │   └── useRegistration.js
│   ├── appointments/
│   │   ├── index.js
│   │   ├── useAppointmentCount.js
│   │   └── useAppointments.js
│   ├── assistant/
│   │   └── index.js
│   ├── auth/
│   │   ├── index.js
│   │   ├── useLogin.js
│   │   └── useSession.js
│   ├── content/
│   │   ├── index.js
│   │   └── usePublicContent.js
│   ├── counselor/
│   │   └── index.js
│   ├── enrollment/
│   │   ├── index.js
│   │   ├── useCorUpload.js
│   │   └── useReviewerConsole.js
│   ├── messaging/
│   │   └── index.js
│   ├── sos/
│   │   └── index.js
│   └── wellness/
│       └── index.js
├── hooks/
│   └── useHealth.js
├── pages/
│   ├── counselor/
│   │   ├── CounselorAppointmentsPage.jsx
│   │   └── counselor_dashboard.jsx
│   ├── student/
│   │   ├── StudentAppointmentsPage.jsx
│   │   └── student_homepage.jsx
│   ├── HomePage.jsx (Compatibility Wrapper)
│   ├── AppointmentsPage.jsx (Compatibility Wrapper)
│   ├── LandingPage.jsx
│   ├── LandingLink.jsx
│   ├── LoginPage.jsx
│   ├── RegisterPage.jsx
│   └── ReviewerPage.jsx
├── services/
│   ├── apiClient.js
│   └── index.js
├── types/
│   └── api.js
├── App.jsx
├── index.css
└── main.jsx
```

---

## 9. Master AI Prompt for Future Restructuring

When prompting future AI instances to work on this frontend codebase, provide them with the following prompt snippet to ensure total adherence to project constraints:

```text
You are working on the CounselConnect frontend (React JavaScript, Vite, TailwindCSS).
CRITICAL RULES & BOUNDARIES:
1. Stack: React (JavaScript) + Vite + TailwindCSS. Do NOT introduce TypeScript, React Router, Next.js, or other routing libraries.
2. Routing: Hash-based routing via window.location.hash in App.jsx. Preserve all existing hash routes (#home, #appointments, #review, #login, #register, #landing).
3. Auth & Security: ADR-019 session-cookie auth. Credentials in HttpOnly cookies; CSRF tokens in memory (with automatic recovery in apiClient.js).
4. Role Separation: target roles are STUDENT, COUNSELOR, and SUPERADMIN. GUIDANCE_STAFF is legacy until the automated COR-screening migration is complete. Never mix Student, Counselor, and Superadmin views or route logic. Counselor clinical views remain assignment-scoped; Superadmin has no default clinical-content access.
5. Counselor Protection: Do not redesign or modify Counselor UI (counselor_dashboard.jsx, CounselorAppointmentsPage.jsx, sidebar) unless explicitly requested.
6. Notification Architecture: Notifications use reusable components in src/components/notifications/ (NotificationBell, NotificationPanel) with role-aware data sourcing in AppNavBar.jsx. Read/unread state uses user-specific localStorage keys (cc_read_notifications_${userId}).
7. Testing & Build: Always run `node --test tests/*.test.cjs` and `vite build` after any changes to verify 100% test passing (47 tests) and clean compilation.
8. Scope Boundary: Never modify backend code, database, or docs outside frontend/.
```
