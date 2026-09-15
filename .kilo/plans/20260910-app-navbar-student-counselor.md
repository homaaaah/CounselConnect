# App Navbar for Student and Counselor (plus Landing Header Polish)

## Context (verified 2026-09-10)

- `App.tsx:36-46` renders a minimal signed-in strip (Appointments / COR verification / Sign out links). This is the only "navbar" for authed users today.
- Working hash routes: `#home`, `#appointments` (STUDENT/COUNSELOR, ACTIVE only), `#review` (COUNSELOR only), public `#landing`, `#login`, `#staff-login`, `#register`.
- `components/layout/index.ts` is a placeholder explicitly reserved for "app shell, navigation, role-aware menus".
- `useSession` already exposes `user`, `idle_expires_at`, `absolute_expires_at`; `/auth/csrf` returns fresh `AuthResult` (used by session restore).
- Pages NOT yet built: Messages, SOS, Wellness Resources, Assistant, Counselor dashboard.
- **In-flight unrelated work (do not touch or commit):** uncommitted changes in `backend/app/modules/appointments/*`, `backend/app/tests/integration/test_appointments.py`, `frontend/src/features/appointments/*`, `frontend/src/pages/AppointmentsPage.tsx`, `frontend/tests/appointments.test.cjs` (past-slot/date-filter refinement). Navbar files do not overlap these.
- `.ai/CURRENT_TASK.md` already describes THIS task as ACTIVE (uncommitted edit). Implementer updates it to COMPLETED at the end; include it in the navbar commit.

## User-confirmed decisions

1. Nav contains working links PLUS disabled "coming soon" entries (Messages, SOS, Resources, Assistant).
2. Current page is highlighted (`aria-current="page"` + emerald active style), mirroring landing `.active` pattern.
3. Mobile: hamburger below md with `aria-expanded`/`aria-controls`, closes on link click and Escape.
4. Session-expiry display: **minimal but clear and noticeable** — small clock pill showing when the session ends, amber escalation near expiry.
5. Non-ACTIVE students see an amber status banner under the navbar explaining why scheduling is locked.
6. Exact "Sign out" button label is preserved (existing tests assert it).

## Deliverables

### 1. NEW `frontend/src/components/layout/AppNavBar.tsx`

Props: `{ user, page, idleExpiresAt, absoluteExpiresAt, onSignOut }`. Sticky top, white bg, bottom border, Tailwind utilities only (matches AppointmentsPage/ReviewerPage styling; landing keeps its scoped CSS).

- **Left:** brand "CounselConnect" → `#home`.
- **Links (role-gated, identical gating to current App.tsx):**
  - All authed roles: Home (`#home`).
  - STUDENT with `account_status === "ACTIVE"`: Appointments (`#appointments`).
  - STUDENT pending/expired: NO Appointments link (banner covers the explanation).
  - COUNSELOR: Appointments (`#appointments`) + COR Verification (`#review`).
  - GUIDANCE_STAFF: Home only (no student-feature entries, no coming-soon set).
  - Coming-soon disabled entries for STUDENT and COUNSELOR: Messages, SOS, Resources, Assistant — non-navigable `<span aria-disabled="true">` with "soon" tag and `title="Coming soon"`, muted styling.
- **Active state:** link matching current `page` gets `aria-current="page"` + emerald text/border. No link active when page is landing/login/etc.
- **Right cluster:** session pill, user chip (First Last + role label), Sign out button (exact label).
- **Session pill (minimal, accurate):** shows earlier of idle/absolute expiry, e.g. "Session ends 3:45 PM" (Asia/Manila via Intl, consistent with `formatSchedule`). Amber + "ends in 5m" style when ≤5 min remain. Re-syncs by polling `GET /auth/csrf` every 60s with header `X-Background-Refresh: 1` (read-only — per ADR-019 this poll must NOT renew idle time; backend already enforces). On poll failure/401: keep last known value, no session clearing (the existing 401 path in apiClient already handles the real expiry). Ticks between syncs via 30s local interval.
- **Pending banner:** when `user.role_code === "STUDENT"` and `account_status !== "ACTIVE"`, slim amber strip under the bar: PENDING_VERIFICATION → "Verification pending — scheduling unlocks after COR approval."; VERIFICATION_EXPIRED → "Enrollment expired — re-verify your COR to restore scheduling."
- **Mobile:** below md, links collapse behind hamburger (`aria-controls="app-nav-links"`); panel closes on link click and Escape; Escape handled via keydown listener gated on open state.

### 2. EDIT `frontend/src/components/layout/index.ts`

Export `AppNavBar` (keep the doc comment about backend authorization being authoritative).

### 3. EDIT `frontend/src/App.tsx`

Replace the inline signed-in strip (lines 36-46) with `<AppNavBar user={session.user} page={page} idleExpiresAt={session.idleExpiresAt} absoluteExpiresAt={session.absoluteExpiresAt} onSignOut={...} />`, keeping the existing logout behavior (call `session.logout()`; on success set hash to landing). Navbar renders whenever `session.user` exists, above page content. Everything else (session restore, hash switcher, page gating, health footer) unchanged.

### 4. EDIT `frontend/src/pages/LandingPage.tsx` (header only, per ACTIVE task)

- Sticky header with scrolled state (shadow/blur via scrolled CSS class on scroll listener).
- Nav links Home/Features/News + add FAQ (add `id="faq"` to the existing FAQ section).
- Scroll-spy: `IntersectionObserver` over `#features`, `#news`, `#faq` sections sets `.active` on the matching link (reuse existing `.active` style).
- Mobile: hamburger toggling `#landing-mobile-nav` drawer (`aria-expanded`, closes on link click/Escape).
- LOG IN button and modal behavior (student login overlay) unchanged.

### 5. EDIT `frontend/src/index.css`

Extend the existing scoped `.landing-page` header block only: sticky positioning, scrolled shadow, mobile drawer styles + media query. Do not touch app-shell sections (AppNavBar is pure Tailwind).

### 6. NEW `frontend/tests/navbar.test.cjs`

Follow the harness style of `session.test.cjs` (`register-typescript.cjs`, fake `window.location`, mocked `fetch`, react-test-renderer). Cover:
1. Counselor at `#home`: greeting "Cora Reyes", chip "Counselor", `aria-current="page"` on Home, Appointments + COR Verification links, Sign out present.
2. Active STUDENT: Home + Appointments links; coming-soon entries are `aria-disabled` and have no `href`.
3. Pending STUDENT: no Appointments link, "Verification pending" chip + banner text present.
4. GUIDANCE_STAFF: Home link only, "Guidance Staff" chip, no coming-soon entries, no banner.
5. Mobile toggle flips `aria-expanded`; drawer link click closes it (landing test).
6. Session pill renders "Session ends" text; amber class appears with a near-expiry timestamp (no timer wait — pass a close expiry prop).
7. Landing: FAQ link present; LOG IN still opens the student login modal.

### 7. `.ai/CURRENT_TASK.md`

Already ACTIVE for this task (uncommitted). On completion, set `Status: COMPLETED` with actual verification results. Commit it with the navbar work.

## Boundaries

- Role visibility is usability only; backend authorization remains authoritative (per `docs/USER_ROLES.md` and the layout index doc comment). No authz logic changes.
- No backend, routing-library, or page-body changes. HomePage body, ReviewerPage content, and appointments code untouched.
- ADR-019 five-minute warning MODAL stays out of scope — the pill is a passive display; the existing 401 session-error path handles actual expiry.
- Known limitation to note in CURRENT_TASK: idle renewal is only re-synced by the 60s poll; between polls the countdown is conservative.

## Git discipline (per `.ai/CONTRIBUTING.md`)

1. `git switch -c frontend/app-navbar` from current `main` (unstaged appointments work carries over harmlessly).
2. Commit ONLY: `AppNavBar.tsx`, `components/layout/index.ts`, `App.tsx`, `LandingPage.tsx`, `index.css`, `tests/navbar.test.cjs`, `.ai/CURRENT_TASK.md`. NEVER `git add .` (would sweep the in-flight appointments files).
3. Push `-u origin frontend/app-navbar`; PR per team workflow.

## Verification

- `npm run build` in `frontend/` (Vite + tsc).
- `npm test` in `frontend/` — all existing tests (10 session + 10 appointments) must still pass, plus the new navbar suite.
- Manual: `npm run dev` → sign in as student/counselor/staff; check active highlight, coming-soon disabled entries, hamburger below md, banner for pending student, session pill countdown, Sign out still works.

## Risk

MEDIUM (localized UI integration; role gating preserved exactly from existing logic; no API/auth/schema change).
