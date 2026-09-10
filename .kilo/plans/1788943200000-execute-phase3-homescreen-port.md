# Execute Phase 3 — Homescreen port into React `#home`

**Risk class:** MEDIUM (UI integration only — no backend/schema/auth changes)
**Route:** `project` + affected frontend code. Parent plan: `.kilo/plans/1788937804000-port-landing-to-react.md` (Phase 3).

## Context (all verified in code)

- `HomePage.tsx` (96 lines): receives `user?: SessionUser | null`; currently a slate-styled services grid + announcements + emergency-contacts panel (`usePublicContent`). No tests reference HomePage, AppointmentsPage mocks, or `#home` (grep-verified) — free to restyle.
- `useAppointments` (features/appointments/useAppointments.ts): full real data hook — `slots` (`Page<Slot>`, `/availability-slots`), `appointments` (`Page<Appointment>`, `/appointments`), campuses, filters, `refresh`, `mutate`, `formatSchedule` (Asia/Manila). Slots carry `counselor_name`, `status: AVAILABLE|RESERVED`.
- `AppointmentsPage.tsx`: the real booking console (filters, SlotCard booking, confirm/reject/cancel/reschedule) — already linked from `#home`'s Schedule button target.
- Homescreen mock (`public/homescreen.html/.css/.js`): design = badge + hero + two CTAs + features row; mock calendar (Oct-2023, fake counselor "Ms. Sarah Jenkins", stale month-selection bug), dead Emergency `href="#"`.
- `App.tsx`: `#home` renders `HomePage user={session.user}`; Sign out bar persists above every page.
- `usePublicContent` also returns `contacts` (real seeded emergency contacts, `/content/emergency-contacts`).

## Design decisions (per parent plan Phase 3, steps 9–11)

1. Port the homescreen **visual design** (badge, hero copy, Schedule + Emergency CTAs, features row) into `HomePage.tsx` — but wire everything to real data; do NOT copy the mock calendar or fake counselor.
2. Schedule CTA → `#appointments` (the real booking flow). Hide/adjust for roles that cannot book (App.tsx already gates the appointments link to ACTIVE STUDENT/COUNSELOR — mirror that logic on the button; show a "verification pending" hint otherwise).
3. Emergency CTA → scrolls to the real emergency-contacts section (`ref.scrollIntoView({ behavior: "smooth" })`); render contacts from `usePublicContent().contacts`. Fixes the dead-link affordance without leaving the page (hash navigation would unmount the page).
4. Real upcoming-appointments strip: for a signed-in user with an ACTIVE STUDENT/COUNSELOR role, fetch via `useAppointments()` and render the next few upcoming appointments (status PENDING/CONFIRMED, sorted by starts_at) as cards with `formatSchedule`, status badge, campus, mode — each linking to `#appointments`. On API failure or empty: quiet empty state ("No upcoming appointments yet."). Non-authorized visitors: section hidden.
5. Counselor identity: show the actual session user's name (`user.first_name`/`last_name`) in any profile-ish element — never the fake "Ms. Sarah Jenkins". If a counselor banner is kept, render `user` when COUNSELOR; students don't need one.
6. Do NOT copy `homescreen.js` bugs: no `alert()` booking, no October-2023 calendar, no stale month state — real availability browsing already lives in `AppointmentsPage`.
7. Scoped CSS: append `.home-page`-prefixed rules (hero/badge/buttons/features/appointment cards) to `frontend/src/index.css`. No bare element selectors (same rule as the landing port).
8. Delete `frontend/public/homescreen.html`, `homescreen.css`, `homescreen.js` (untracked → targeted `git clean -f -- <paths>`; verify `git status`).
9. `.ai/CURRENT_TASK.md`: ACTIVE entry before code, COMPLETED after verification (per workflow rules).
10. `CHANGELOG.md`: add the Phase 3 session entry; move homescreen items out of "Open items".

## Steps

1. Write ACTIVE `.ai/CURRENT_TASK.md` (objective/route/scope/criteria/verification as above).
2. Rewrite `frontend/src/pages/HomePage.tsx`:
   - Keep the `user` prop signature and `usePublicContent` usage; add `useAppointments` for authorized users.
   - Structure: `.home-page` wrapper → header hero area (badge "Confidential student support services", h1 "Your mental well-being matters to us.", supporting paragraph), action buttons (Schedule → `#appointments` or verification hint; Emergency → scroll to contacts), features row (Fully Private / 24/7 Support / Video-In-person — keep as informational, they describe services, not dead actions), upcoming-appointments strip (step 4), announcements (existing), emergency-contacts section with `ref` for the scroll target.
   - Keep the "services unlock after verification" DFD note for PENDING users.
3. Append `.home-page` styles to `frontend/src/index.css` (adapt the homescreen.css palette: `--primary` green badge, emergency `--accent` outline button; reuse existing `:root` tokens).
4. Delete the three `public/homescreen.*` files.
5. Update `CHANGELOG.md` + finalize `.ai/CURRENT_TASK.md`.

## Verification

1. `npm run build` — React bundle; `dist/` root must contain ONLY `.gitkeep` from public/ (homescreen statics gone).
2. `npm test` — 16/16 (nothing test-visible changes).
3. Dev server: `/homescreen.html` 404 (SPA fallback serves index — confirm via served content, and `dir` shows no file); `#home` renders the design (student login → redirect lands there).
4. Live (if backend available): signed-in student sees upcoming-appointments strip; Emergency scrolls to seeded contacts; Schedule reaches the real booking console.
5. MEDIUM-risk in-task review: re-read final diff — no mock leftovers, no element-selector leaks, no dead buttons.

## Acceptance criteria

- `#home` = homescreen design + real data; fake counselor/calendar/alerts gone; Emergency functional; statics deleted; build + tests green; task docs updated.
