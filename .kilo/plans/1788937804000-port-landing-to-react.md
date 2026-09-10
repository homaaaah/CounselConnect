# Port the Capstone landing design into the React app

**Risk class:** MEDIUM (localized application behavior / UI integration; presentation only — no backend, schema, or auth-logic changes; all session/role/auth code is reused unchanged and already tested)
**Route:** `project` (`.ai/PROJECT.md`) + affected frontend code and tests.

## Why

The static Capstone landing (merged 2026-09-09) is session-blind and unserved the React
SPA: the Appointments nav, Sign out button, and the counselor Approve/Reject console
(all in `src/App.tsx`) are unreachable. The Capstone docx §6 records the agreed fix:
"Porting this design INTO React components is the agreed next step." This plan merges
the two halves — the React app's tested functionality and the Capstone design — into
one canonical app.

## What this plan resolves (from the review / open-items list)

- React SPA unserved at `/` → entry restored.
- `docs/TEAM_SETUP_GUIDE.md` demo flow (`#login`/`#review`/`#appointments`) and the
  step-5 "landing shows seed content" check become accurate again — **no doc edits
  needed** (the guide was written for the React app).
- Global `header`/`footer` element selectors in `src/index.css` that would restyle
  React pages → all landing styles namespaced under `.landing-page`.
- `landing-api.js` + `public/login_modal.html` / `signup_modal.html` duplication of
  tested hooks → deleted.
- `counselconnect-frontend/` not gitignored (one `git add -A` commits ~200 stale
  duplicates) → one-line `.gitignore` fix bundled into cleanup.

## Facts the implementation relies on (verified in code)

- `App.tsx` renders `LandingPage` for every unknown hash incl. `landing` (line 61),
  and session-aware nav (Appointments link line 38, Sign out line 42) once
  `session.user` exists. Hash pages: `login`, `staff-login`, `register`, `home`,
  `review`, `appointments`.
- `LoginPage.tsx` redirects by role after ~700 ms: `COUNSELOR → #review`,
  `STUDENT → #home`, else `#landing`; separate student (student number) vs staff
  (email) forms via `audience` prop.
- `RegisterPage.tsx` + `useRegistration` already implement the full contract
  (API-driven campuses/programs, years 1–6, COR PDF upload) — identical to what
  `landing-api.js` hand-implemented.
- `useSession` restores via `POST /auth/csrf` on mount; App blocks protected pages
  until `ready`.
- `main.tsx` imports `./index.css` — that's why CSS namespacing is mandatory.
- Frontend tests (`tests/*.test.cjs`) require `../src/App.tsx` directly and never touch
  `index.html` — the landing swap cannot break them structurally.
- Old `LandingPage.tsx` is CMS-driven (`usePublicContent`: hero block, announcements,
  FAQs) and the setup guide's step-5 check depends on that data appearing.

## Design decisions (recommendation; confirm at kickoff if disputed)

1. **Auth as styled hash pages, not modals.** Keep `LoginPage`/`RegisterPage` routes
   (session logic, role redirects, and 16 tests depend on them); restyle them with the
   Capstone card classes (`.modal-card`, `.signup-card`, `.form-input`, `.form-select`,
   `.btn-submit`, `.upload-box` — already global classes in `index.css`). The landing
   LOG IN / CONNECT WITH US buttons link to `#login` / `#register`.
2. **CMS content mapped into the Capstone layout** (keeps the guide's step-5 check
   truthful): hero `<p>` uses `hero?.body` with the Capstone copy as fallback; the
   Blog grid renders real `announcements` (category "Announcement"); a FAQ strip
   below renders real `faqs` using the same card styles. Bio section and footer
   contact details stay Capstone placeholders (real content is a CMS/team decision).
3. **CSS namespacing:** wrap the landing JSX in `<div className="landing-page">`; in
   `src/index.css` scope every landing rule under `.landing-page` (incl. the bare
   `header`/`footer` element rules → `.landing-page header { … }`); drop the global
   `*` and `body` rules (Tailwind preflight already provides that baseline); keep
   `:root` variables (inert unless referenced); keep auth-card class rules global
   (classes don't leak; only element selectors do).
4. **Dev links:** keep a subtle "Counselor review console (dev)" link (team uses it);
   drop the old "Preview the signed-in homepage" button (real sign-in exists).

## Phases

### Phase 1 — Port the landing into React (the bulk)

1. `.ai/CURRENT_TASK.md` → new ACTIVE entry (objective, route, scope, criteria, verification).
2. Rewrite `frontend/src/pages/LandingPage.tsx` as the Capstone layout in JSX:
   - Header: logo, Home/Features/News anchors (`id="features"`, `id="news"` on sections),
     LOG IN → `#login`.
   - Hero: `<i>Gentle Support</i>…` headline, CMS hero body (fallback to Capstone copy),
     CONNECT WITH US → `#register`.
   - Why-choose-us (3 static cards), Bio (placeholder), Blog grid (announcements),
     FAQ strip (faqs), Footer (Capstone placeholders + subtle dev `#review` link).
   - Reuse `usePublicContent`; keep `onPreviewHome` prop out (decision 4).
3. Namespace `frontend/src/index.css` (decision 3). No React page may be affected by
   element selectors — verify `AppointmentsPage.tsx:153` bare `<header>` renders
   unstyled as before.
4. Restyle `LoginPage.tsx` / `RegisterPage.tsx` shells with Capstone card classes
   (keep all logic, ids, hooks, autocomplete, tests intact; only the wrapper markup
   and class names change). Keep their existing behavior text (role routing, links).
5. `frontend/index.html` becomes the Vite React entry again (12-line form) plus the
   Font Awesome CDN `<link>` (icons used by the landing) and `<title>CounselConnect</title>`:
   `<div id="root"></div>` + `<script type="module" src="/src/main.tsx"></script>`.
   (Absolute `/src/…` path — Vite rewrites it correctly for both dev and build.)

### Phase 2 — Remove the now-duplicated static wiring

6. Delete `frontend/landing-api.js` (its contract lives in tested hooks).
7. Delete `frontend/public/login_modal.html` and `frontend/public/signup_modal.html`
   (nothing fetches them anymore).
8. Keep `frontend/public/homescreen.*` for now (Phase 3 decides their fate; nothing
   links to them after this phase).

### Phase 3 — Homescreen port (deferrable; schedule separately if desired)

9. Restyle `frontend/src/pages/HomePage.tsx` (already receives `user`) with the
   homescreen design and wire it to the real appointments API
   (`useAppointments` / `AppointmentsPage` patterns — availability, booking,
   approval states) instead of the mock counselor/Oct-2023 calendar.
10. While porting, fix (do not copy) the two mock bugs: stale
    `selectedDate`/`selectedTimeSlot` across month navigation, and the dead
    Emergency button (wire to seeded emergency contacts or remove).
11. Delete `frontend/public/homescreen.html/.css/.js` once the React home exists.
    Logout: App's Sign out (already present) covers it.

### Phase 4 — Cleanup, verification, docs

12. Add `counselconnect-frontend/` to root `.gitignore` (one line; prevents committing
    the ~200-file stale duplicate tree).
13. Update `CHANGELOG.md` open-items list (items 1, 2, 5 resolved; 4 resolved by 12;
    3 resolved if Phase 3 done, else still open).
14. `.ai/CURRENT_TASK.md` → COMPLETED with actual verification results.

## Explicitly out of scope

- Backend code, DB schema, auth/session logic, role rules, or any `.ai` contract doc.
- ADR-P02 transport, password-reset email (ADR-P09), social logins (stay decorative).
- Real counselor bio / footer contact content (CMS/team decision, placeholder kept).
- The homescreen mock bugs (unless Phase 3 is executed in the same pass).
- No changes to `backend/`, `contracts/`, `db/`, `design/`, `docs/` contracts.

## Verification plan (run what applies per phase)

1. `npm run build` — must emit the React app bundle from `index.html`
   (`dist/assets/index-*.js` grows to include React; only `homescreen.*` + `.gitkeep`
   remain in `dist/` root from `public/`).
2. `npm test` — 16/16 must pass (they exercise login/register/appointments/reviewer
   through `App.tsx`, independent of `index.html`).
3. Dev-server checks: `/` shows the Capstone-styled landing; no console errors;
   `#login`, `#register` render the styled auth cards; `/landing-api.js` 404s (deleted).
4. CSS regression check: `#appointments` page (as an ACTIVE student/counselor) — the
   bare `<header>` must NOT show the landing navbar styling.
5. Live flow (backend + MySQL running; skip honestly if not): register student with
   PDF via `#register` → counselor login via `#login` → `#review` shows the
   application with Approve/Reject → approve → student login lands on `#home` →
   Appointments nav + Sign out visible. This restores the exact
   `docs/TEAM_SETUP_GUIDE.md` demo flow.
6. MEDIUM-risk in-task review: re-read the final diff against this plan (scope,
   namespacing completeness, no logic edits in the auth pages) before reporting.

## Acceptance criteria

- `/` serves the React app with the Capstone landing design; React pages
  (`#login`, `#register`, `#home`, `#appointments`, `#review`) are all reachable.
- Session-aware UI is back: Appointments link (ACTIVE student/counselor), Sign out,
  counselor Approve/Reject console — with zero auth-logic changes (diff touches
  markup/classes only in auth pages).
- CMS content (hero/announcements/FAQs) still renders on the landing (guide step-5
  check holds).
- No landing element-selector CSS leaks into other React pages.
- `landing-api.js`, `public/login_modal.html`, `public/signup_modal.html` deleted;
  `counselconnect-frontend/` gitignored.
- Build + 16/16 tests green; live demo flow (if run) completes.
- `.ai/CURRENT_TASK.md` documents the task; CHANGELOG open items updated.

## Rollback

Everything is uncommitted and duplicated in `counselconnect-frontend/` (and git
history holds the pre-merge React entry), so any phase can be paused or reverted
without losing work.
