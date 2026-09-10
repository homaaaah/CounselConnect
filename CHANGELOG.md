# Changelog — CounselConnect

Working-tree changes from the recent working sessions (2026-09-08 → 2026-09-09).
All changes are **uncommitted** and awaiting team review/PR per `.ai/CONTRIBUTING.md`.

---

## 2026-09-09 — Static landing page wired to the backend (plain JavaScript)

**Goal:** make the landing page's login/signup modals actually call the FastAPI backend
without touching the React app. Plan: `.kilo/plans/1788931024000-wire-landing-to-backend.md`.

### Added
- `frontend/landing-api.js` — Vite-processed ES module:
  - API client mirroring `src/services/apiClient.ts` (ADR-019): `credentials: "include"`,
    in-memory CSRF echoed via `X-CSRF-Token`, standard error-envelope parsing,
    `NETWORK_ERROR` fallback.
  - Modal fetch/DOMParser loader + open/close/switch/overlay-click wiring.
  - Login submit → `POST /auth/login` `{identifier, password}`; success shows
    "Signed in as {first} {last}." then redirects to `./homescreen.html` (~700 ms).
  - Signup submit → `POST /accounts/register/student-with-cor` multipart
    (numeric `campus_id`/`program_id`/`year_level` + `file` COR PDF).
  - Campus/program selects populated from `GET /accounts/campuses` / `GET /accounts/programs`.
  - Client-side COR guard (PDF only, ≤ 10 MB) and friendly mappings for
    `EMAIL_ALREADY_REGISTERED`, `STUDENT_NUMBER_ALREADY_REGISTERED`,
    `COR_MUST_BE_PDF`, `COR_INVALID_PDF`, `COR_TOO_LARGE`.
  - Password eye toggle; double-submit button guard.

### Changed
- `frontend/index.html` — 100+ line inline `<script>` replaced with
  `<script type="module" src="./landing-api.js"></script>` (zero inline JS remains).
- `frontend/public/login_modal.html` — identifier field relabeled **"Student number or
  email"** (backend accepts either per ADR-005/019); added ids/names,
  `autocomplete` attributes, inline message area; removed `onsubmit` stub.
- `frontend/public/signup_modal.html` — added ids/names/validation attributes;
  **hardcoded campus/program options replaced with API-driven selects** (fixes the
  divergence from seeded reference data found in review); year levels 1–6 to match
  the canonical register form; removed `onsubmit` stub.
- `frontend/src/index.css` — appended `.form-message` success/error feedback styles
  (Tailwind directives untouched).

### Moved
- `login_modal.html`, `signup_modal.html`, `homescreen.html`, `homescreen.css`,
  `homescreen.js` from `frontend/` root → `frontend/public/` so `vite build` emits
  them into `dist/` (**fixes the deploy-safety review finding**: runtime-fetched
  modals 404'd in built deployments and Capacitor `webDir: "dist"`).

### Verification (all run)
- `npm run build` — `dist/` now contains the bundled JS + all five static files.
- `npm test` — 16/16 pass (React tree untouched).
- Dev-server asset checks — all wired URLs return 200.
- **Live backend flow** (backend + MySQL running): CORS preflight OK; seeded-counselor
  login returns full `AuthResponse` + HttpOnly `counselconnect_session` cookie;
  wrong password → `INVALID_CREDENTIALS` (renders inline); student registration with
  PDF → 201 `PENDING_VERIFICATION` + `next_step` message; duplicate email → mapped
  error; newly-registered (PENDING) student can log in — intended backend behavior
  (`auth/service.py:46`).

### Side effects
- A test student row now exists in the dev DB: user_id 5, `2026-99901`,
  `live-probe-20260909@ucc.edu.ph` (COR stored under `backend/var/cor`).
  Delete via MySQL if undesired.

---

## 2026-09-09 — Post-merge advisory review (no code changed)

Full review of the uncommitted tree (9 findings). Outcomes:
- **Fixed in the wiring session above:** modal partials missing from `dist/`
  (→ `public/` move); signup reference-data divergence (→ API-driven selects).
- **Still open (see Open Items):** homescreen stale month-selection bug; dead
  Emergency button; `docs/TEAM_SETUP_GUIDE.md` demo flow vs static page;
  `counselconnect-frontend/` not gitignored; global `header`/`footer` element
  selectors in `index.css` that will restyle React pages once re-served.

---

## 2026-09-09 — Capstone landing merged into main repo

**Goal:** merge the `counselconnect-frontend/` copy (basis: `Capstone-Project-Documentation.docx`
+ copy's `.ai/CURRENT_TASK.md` modal-split log; homescreen prototype included by user
decision). Plan: `.kilo/plans/1788929294938-merge-capstone-frontend-into-main.md`.

### Added (to `frontend/`)
- `index.html` — **replaced** the 12-line Vite React entry with the 321-line Capstone
  static landing page (header/hero/why-choose-us/bio/blog/footer + modal loader).
  *Known consequence: the React SPA is no longer served at `/`; porting the design
  into React components is the agreed next step (docx §6).*
- `src/index.css` — **replaced** the 3-line Tailwind-only file with the 738-line
  stylesheet (Tailwind directives retained at top; landing + modal styles appended).
- `login_modal.html`, `signup_modal.html` — modal partials (documented modal-split session).
- `homescreen.html` / `.css` / `.js` — standalone "UniCounsel" schedule-page prototype
  (user-approved inclusion; undocumented in `.ai/`).

### Kept intentionally (copy was stale)
- Main's newer docs-sync state: root `README.md`, `docs/TEAM_SETUP_GUIDE.md`,
  `docs/REAL_TIME_MESSAGING.md`, `.ai/*` (except CURRENT_TASK.md).
- `frontend/package-lock.json`, `backend/`, `contracts/`, `db/`, `design/`,
  all React `src/**`, tests, configs — byte-identical in the copy.
- `tsconfig.tsbuildinfo` (build artifact) not copied; copy folder retained on disk.

### Verification
- Line-by-line fidelity check of all 7 file pairs (identical; 321/738/60/103/165/519/164 lines).
- `git status` scope check — only intended files changed.
- `npm run build` + `npm test` — pass (16/16).

---

## 2026-09-08 — Docs sync (appointments + messaging)

Session that produced the (still-uncommitted) documentation updates present in the
working tree:

### Changed
- `docs/REAL_TIME_MESSAGING.md` — noted implemented status: the messaging service
  validates participant/mode/type linkage and closes conversations on authorized
  terminal outcomes; conversation creation awaits the ADR-P02 transport decision.
- `docs/TEAM_SETUP_GUIDE.md` — baseline-SQL + `alembic stamp 8f0f8c585641` setup flow
  (22 tables incl. `user_sessions`); student-number vs staff-email sign-in explanation;
  optional appointments demo step; team Git workflow (branch-per-task + PR) replacing
  `git add -A` push-to-main guidance; updated quick reference.
- `README.md` — `contracts/` description (generated OpenAPI snapshot); refreshed
  pending-decisions list (ADR-P02…P09); "Local setup" section; CONTRIBUTING pointer.
- `.ai/PROJECT.md` — restored correct project-context content (file previously held
  duplicated naming-conventions text).
- `.ai/NAMING_CONVENTIONS.md` — added `user_sessions`/`session` identifiers and column
  set; Counselor SOS availability values (`AVAILABLE`/`BUSY`/`UNAVAILABLE`); auth route
  exceptions (`/auth/me`, `/auth/csrf`, password-recovery actions).
- `.ai/DECISIONS.md` — added pending **ADR-P09** (Capacitor session-credential
  transport and production password-reset email delivery/fallback).
- `.ai/README.md` — added `CONTRIBUTING.md` row to the `.ai` file map.

---

## 2026-09-10 — Capstone landing ported INTO React (single canonical app)

**Goal:** restore the session-aware React app at `/` wearing the Capstone design —
the docx §6 "agreed next step". Plan: `.kilo/plans/1788937804000-port-landing-to-react.md`.

### Changed
- `frontend/index.html` — Vite React entry restored (`#root` + `/src/main.tsx`),
  keeping the Font Awesome CDN `<link>` (landing icons). The 321-line static
  landing page is retired from the entry.
- `frontend/src/pages/LandingPage.tsx` — rewritten as the Capstone layout in JSX
  (header/hero/why-choose-us/bio/blog/footer) inside a `.landing-page` wrapper;
  CMS content mapped in: hero paragraph uses `landing_hero` body (Capstone copy
  fallback), blog grid renders published **announcements**, new FAQ strip renders
  published **FAQs**; subtle dev `#review` link kept; `onPreviewHome` prop removed.
- `frontend/src/index.css` — fully namespaced: ALL landing rules scoped under
  `.landing-page` (fixes the global element-selector leak — bare `header`/`footer`
  rules that would have restyled React pages are gone); auth card classes kept as
  global class rules (shared by the styled auth pages); added `.auth-shell` and
  FAQ/blog-empty styles.
- `frontend/src/pages/LoginPage.tsx` / `RegisterPage.tsx` — restyled with the
  Capstone card classes (`.modal-card`/`.signup-card`, `.form-input`, `.btn-submit`,
  `.upload-box`); **all logic, hooks, ids, autocomplete, role-redirect behavior, and
  test-relevant markup unchanged**.
- `frontend/src/App.tsx` — one line: dropped the dead `onPreviewHome` prop.

### Deleted
- `frontend/landing-api.js` (contract lives in tested hooks), `frontend/public/login_modal.html`,
  `frontend/public/signup_modal.html` — the duplicate static auth implementation.
- `frontend/public/homescreen.*` KEPT (Phase 3 homescreen port still pending).

### Added
- `counselconnect-frontend/` → root `.gitignore` (duplicate-tree hazard closed:
  `git add -A` can no longer stage ~200 stale files).

### Restored by this port
- React SPA at `/`: Appointments link (ACTIVE student/counselor), Sign out,
  counselor Approve/Reject console (`#review`), student/counselor role redirects —
  all session-aware UI the static page couldn't render.
- `docs/TEAM_SETUP_GUIDE.md` demo flow (`#login`/`#review`/`#appointments`) and the
  step-5 seed-content check are accurate again — **no doc edits were needed**.

### Verification (all run 2026-09-10)
- `npm run build` — 51 modules transformed; React bundle 188.63 kB; `dist/` =
  `index.html` + assets + homescreen statics only.
- `npm test` — 16/16 (LoginPage restyle preserved every selector contract:
  `htmlFor="identifier"`, `id="identifier"`/`id="password"`, audience `h1`, form
  `onSubmit`).
- Dev server: `/` serves the React entry (confirmed markup), `/landing-api.js`
  404s to the SPA fallback (file gone from disk), `/homescreen.html` still 200.
- CSS regression: compiled stylesheet contains only `.landing-page`-scoped rules +
  Tailwind preflight — the appointments page bare `<header>` is untouched.
- **Live flow** (backend already running on :8000): `/content/announcements` (2
  items) and `/content/faqs` (6 items) return seed data the landing renders;
  counselor login → session cookie → `GET /enrollment-verifications/pending`
  returns 2 PENDING applications (including a real teammate signup,
  `delacruzhomer17@gmail.com` — the wired signup form was used in production
  after 2026-09-09).

---

## 2026-09-10 — Phase 3: homescreen design ported into React `#home`

**Goal:** replace the standalone homescreen mock with the design wired to real data.
Plan: `.kilo/plans/1788943200000-execute-phase3-homescreen-port.md` (Phase 3 of
`.kilo/plans/1788937804000-port-landing-to-react.md`).

### Changed
- `frontend/src/pages/HomePage.tsx` — rewritten in the homescreen design (badge,
  hero, Schedule + Emergency CTAs, features row) with real data:
  - **Upcoming-appointments strip** via `useAppointments` (ACTIVE STUDENT/COUNSELOR
    only): next 3 PENDING/CONFIRMED future appointments with Philippine-time
    formatting, status badges, "Manage appointments" link.
  - **Schedule CTA** → `#appointments` for authorized users; verification-pending
    hint otherwise; guest → `#login`.
  - **Emergency CTA** → smooth-scrolls to the real seeded emergency-contacts
    section (`scrollIntoView`, no page unmount) — **fixes the dead-link
    safety affordance**; contacts render from `/content/emergency-contacts`.
  - Announcements section kept (CMS).
  - Session-user identity only — the fake "Ms. Sarah Jenkins" counselor is gone.
- `frontend/src/index.css` — appended `.home-page`-scoped styles (no element
  selectors; same namespacing rule as the landing).

### Deleted
- `frontend/public/homescreen.html/.css/.js` — the standalone mock (fake
  counselor, hardcoded October-2023 calendar, `alert()` booking). Its
  stale-month-selection and dead-Emergency bugs are **not** copied: real
  availability browsing lives in `AppointmentsPage`, and Emergency is wired.

### Verification (all run 2026-09-10)
- `npm run build` — 51 modules; `dist/` root now ONLY `.gitkeep` (all statics gone).
- `npm test` — 16/16.
- Dev server: `/homescreen.html` falls through to the SPA (mock gone from disk);
  `#home` module serves.
- Live (backend on :8000): `/content/emergency-contacts` → 6 seeded rows (Emergency
  target); counselor `/appointments` → 200 empty list (strip empty state); fresh
  login after session expiry → 200.

---

## 2026-09-10 — Landing auth modals (login/register as overlays)

**Goal:** restore the Capstone modal UX on the React landing — LOG IN / CONNECT
WITH US open the auth pages as in-page modal overlays instead of navigating away.
Plan: `.kilo/plans/1788944100000-execute-landing-auth-modals.md`.

### Changed
- `frontend/src/pages/LoginPage.tsx` — optional `inModal`/`onClose`/
  `onSwitchAudience`/`onSwitchToRegister` props: same card renders without the
  full-page shell, close button, in-modal audience/register switches (`.linklike`
  buttons). Default full-page rendering (incl. all test-contract anchors) unchanged.
- `frontend/src/pages/RegisterPage.tsx` — same `inModal` pattern with an in-modal
  "Sign in" switch; full-page rendering unchanged.
- `frontend/src/pages/LandingPage.tsx` — LOG IN and CONNECT WITH US become buttons
  opening the overlays; modal state `{kind, audience}`, overlay click-outside close,
  Escape close, `key={audience}` resets the login form on audience switch;
  `onSignedIn` (→ `session.accept`) threads through so in-modal login updates the
  session and the existing role-redirect effect (hash → `#home`/`#review`) takes over.
- `frontend/src/App.tsx` — one line: `<LandingPage onSignedIn={session.accept} />`.
- `frontend/src/index.css` — appended `.modal-overlay`, `.modal-close`, `.linklike`
  (class rules only; overlay cards get max-height/scroll).

### Kept intact
Full-page `#login`/`#staff-login`/`#register` hash routes (tests +
TEAM_SETUP_GUIDE demo flow use them); all auth/session logic; register success
shows the backend `next_step` message inside the modal.

### Verification (all run 2026-09-10)
- `npm run build` — 51 modules; 192.01 kB JS / 26.64 kB CSS.
- `npm test` — 16/16 (full-page LoginPage contracts: `#staff-login` href,
  identifier label/ids, audience `h1`, 700 ms role redirect).
- Dev server: all three modules serve; served LandingPage contains the overlay
  wiring (`modal-overlay`, `openLogin`, Escape handler, both switches).
- Modal open/close/switch interactions are client-side state — browser check left
  to the user.

---

## Open items (known, not yet done)

1. Decorative-only UI: social login buttons, "Forgot Password?", "Remember me"
   (password-reset email awaits ADR-P09).
2. `npm audit`: 4 vulnerabilities (1 moderate, 2 high, 1 critical) in pre-existing
   dependencies — unaddressed.
3. Dev DB holds two PENDING registrations (user_id 5 synthetic probe, user_id 6
   real teammate signup) awaiting counselor review or cleanup via MySQL.
4. Optional landing blend-in: CMS hero **title** + office subtitle in the header
   (currently only the hero body is CMS-driven; Capstone copy is the fallback).

---

## Workflow records

- `.ai/CURRENT_TASK.md` — updated at each task boundary (merge → wiring; both COMPLETED).
- `.kilo/plans/1788879742329-docs-sync-appointment-scheduling.md`,
  `.kilo/plans/1788929294938-merge-capstone-frontend-into-main.md`,
  `.kilo/plans/1788931024000-wire-landing-to-backend.md`,
  `.kilo/plans/1788937804000-port-landing-to-react.md`,
  `.kilo/plans/1788943200000-execute-phase3-homescreen-port.md`,
  `.kilo/plans/1788944100000-execute-landing-auth-modals.md` — task plans.
- `Capstone-Project-Documentation.docx` — user-provided merge basis at repo root (untracked).

---

Note on placement: the project's docs guide doesn't define a changelog file, so root
`CHANGELOG.md` is a new convention — if the team prefers it under `docs/`, move it
there and add a row to `docs/README.md` per the guide's "files added" rule.
