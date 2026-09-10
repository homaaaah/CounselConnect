# CounselConnect — Current Task

**Status:** COMPLETED — 2026-09-10
**Risk class:** MEDIUM (UI integration; auth logic reused unchanged from tested components)

## Objective

Open login/register as modal overlays on the landing page (Capstone modal UX): landing LOG IN / CONNECT WITH US buttons open in-page modals instead of navigating away. Full-page `#login`/`#staff-login`/`#register` hash routes remain intact. Plan: `.kilo/plans/1788944100000-execute-landing-auth-modals.md`.

## What was done (2026-09-10)

1. `LoginPage.tsx` — optional `inModal`/`onClose`/`onSwitchAudience`/`onSwitchToRegister`; modal mode renders the same card without the `auth-shell`, adds the close button and in-modal switches; full-page mode unchanged (all test-contract anchors intact).
2. `RegisterPage.tsx` — same pattern with in-modal "Sign in" switch; full-page unchanged.
3. `LandingPage.tsx` — LOG IN / CONNECT WITH US buttons open the overlays; modal state `{kind, audience}`; overlay click-outside + Escape close; `key={audience}` resets the login form on audience flip; `onSignedIn` threads to `session.accept` so login updates the session, then the existing role-redirect effect navigates.
4. `App.tsx` — `<LandingPage onSignedIn={session.accept} />` (one line).
5. `index.css` — appended `.modal-overlay`, `.modal-close`, `.linklike` (class rules only).

## Verification (all actually run 2026-09-10)

- `npm run build`: PASSED — 51 modules; 192.01 kB JS / 26.64 kB CSS.
- `npm test`: PASSED — 16/16 (full-page LoginPage contracts: `#staff-login` href, `htmlFor="identifier"`, `id="identifier"`/`id="password"`, audience `h1`, 700 ms role redirect).
- Dev server: all three page modules serve (200); served LandingPage module contains `modal-overlay`, `openLogin`, Escape handler, and both modal switches (verified in served output).
- Modal open/close/switch interactions are client-side state — browser confirmation left to the user (honestly recorded).

## Remaining limitations

- Register success keeps the modal open showing `next_step` (by design — counselor review is the next step; no auto-login).
- `#staff-login` full-page route still exists for direct links; in-modal staff switch covers the same flow from the landing.
- Changes uncommitted for team review (`.ai/CONTRIBUTING.md`).
