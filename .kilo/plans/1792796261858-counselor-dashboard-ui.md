# Counselor Dashboard — cap today's list, enable weekly volume, reposition cards

## Goal

Three presentation/behavior changes on the Counselor dashboard
(`frontend/src/pages/counselor/counselor_dashboard.jsx`,
`frontend/src/features/counselor/useCounselorDashboard.js`):

1. **Today's appointments** renders at most 5 rows, with a "Showing 5 of N" footer when more exist.
2. **Weekly appointment volume** renders real data instead of its empty state.
3. **Availability update** and **Case distribution** are repositioned.

No backend, API contract, or schema change. `GET /appointments` already provides every field used.

## Decisions (confirmed with the user)

- **Layout — swap the right rail.**
  - Row 2: Today's appointments (2/3) + **Case distribution** (1/3).
  - Row 3: Weekly appointment volume (2/3) + **Availability update** (1/3).
- **Volume series — own appointments, current Manila week, no center average.**
  Mon–Sun of the current Philippine week; future days are `0`. Excludes `CANCELLED` and `REJECTED`.
  The dashed "center average" line and its caption are removed (a Counselor's `GET /appointments` is
  self-scoped — `backend/app/modules/appointments/repository.py:391-397` — so no center average exists).
- **Cap affordance — "Showing 5 of N" footer** linking to `#history` whenever `N > 5`.

## Current state (read before editing)

| File | Relevant code |
|---|---|
| `frontend/src/pages/counselor/counselor_dashboard.jsx` | `TodayAppointments` (92-120), `AvailabilityWidget` (122-133), `WeeklyVolumeChart` (135-153), `CaseDistributionChart` (155-183), page grid (196-233) |
| `frontend/src/features/counselor/useCounselorDashboard.js` | today loader with full pagination (37-77), null placeholders `weeklyVolume`/`caseDistribution` (84-88) |
| `frontend/src/features/appointments/useAppointments.js` | `manilaToday` (9), `formatSchedule` (4) |
| `frontend/src/features/appointments/useAppointmentCount.js` | KPI cards; unaffected |

`weeklyVolume` is `null` today, so `WeeklyVolumeChart` always renders "No weekly appointment volume yet."
`caseDistribution` stays `null` (out of scope) and keeps its empty state after the move.

## Ordered tasks

### 1. Cap today's list — presentation only

In `counselor_dashboard.jsx` `TodayAppointments`:

- Render `today.items.slice(0, 5)` (the hook already sorts by start time).
- When `today.items.length > 5`, render a footer under the list:
  `Showing 5 of N · <a href="#history">View all appointments</a>` (same emerald link styling as the header link).
- **Do not truncate in the hook.** `WelcomeBanner` (67-71) derives "N appointments today" and "N awaiting your review"
  from `today.items`, so the hook must keep returning the complete day.

### 2. Weekly volume data — `useCounselorDashboard.js`

- Extract the existing page-through logic (50-67) into a small local helper (not exported), e.g.
  `fetchPaged(query, isCancelled)` returning all collected items; keep `page_size=100` and the `page <= 20` bound.
- Add a second effect (independent of the today effect) keyed on `user?.user_id`:
  1. `today = manilaToday()`; derive the **Monday of the current Manila week** from those `YYYY-MM-DD` parts
     (`Date.UTC(y, m-1, d)`, `dow = getUTCDay()`, `back = (dow + 6) % 7`, subtract `back` days). Manila has no DST.
  2. `startsAfter = new Date("<monday>T00:00:00+08:00").toISOString()`,
     `endsBefore = new Date(<monday Manila midnight> + 7 * 86400000).toISOString()`.
  3. Fetch `GET /appointments?page=<n>&page_size=100&starts_after=…&ends_before=…` to exhaustion.
  4. Drop `status === "CANCELLED"` and `"REJECTED"`.
  5. Bucket by Manila day (`Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" })`) into `myCases[0..6]`
     (Mon→Sun); missing days are `0`.
- Replace the `weeklyVolume: null` return with `{ myCases, loading, error }`.
- On failure set `error` and leave `myCases` empty — never present a failed week as an empty week.
- Update the hook's header comment: the weekly series now comes from `GET /appointments` with the documented
  range filters; solved/ongoing/distribution still have no source.

### 3. Chart component — `WeeklyVolumeChart`

- Accept `{ myCases, loading, error }`:
  - `loading` → `role="status"` "Loading weekly appointment volume…".
  - `error` → `role="alert"` with the message (reuse the page's red-text style).
  - no data → keep the current "No weekly appointment volume yet." empty state.
  - otherwise render the SVG for 7 values (an all-zero week renders a flat line — the chart stays "enabled").
- Remove the `centerAverage` series and its conditional dashed polyline.
- Keep `role="img"` + `aria-label="Weekly appointment volume"` on the SVG.
- Add a visually hidden per-day summary (`<ul className="sr-only">` with `Mon: 2`, …) so the values are
  screen-reader available **and** assertable without parsing SVG geometry.

### 4. Layout — `CounselorDashboard` grid (196-233)

- Row 2: `TodayAppointments` in `lg:col-span-2`; **Case distribution** section in `lg:col-span-1`
  (unchanged heading, caption, and `CaseDistributionChart` with `caseSegments`).
- Row 3: **Weekly appointment volume** section in `lg:col-span-2`; `AvailabilityWidget` in `lg:col-span-1`.
- Change the volume subtitle from "Your cases versus the center average." to
  "Appointments per day this week (Philippine time)."
- Update the file docstring to describe the new order.
- Do not touch the stat cards, the welcome banner, or the network-failure alert (206).

### 5. Tests — new `frontend/tests/counselor-dashboard.test.cjs`

Follow the repo test conventions: `require("./register-app.cjs")` first, `node:test`, `react-test-renderer`,
`act`, and `t.after` cleanup. Derive all dates from `manilaToday()`/`Intl` — do not hardcode calendar dates
(this repo already has a date-rot failure class).

Mock `global.fetch` with a router that honours the query:

- `/appointments` — if `starts_after`/`ends_before` span one day, return the "today" set; if they span seven days,
  return the week set; respect `page`/`page_size` and `total`.
- `/accounts/students` — `{ items: [], total: 0, page: 1, page_size: 1 }`.

Cases to assert:

1. **Cap + footer:** 7 appointments today → exactly 5 rows rendered, banner still says "7 appointments today",
   footer reads `Showing 5 of 7` and links to `#history`. With 5 or fewer, no footer.
2. **Volume renders:** the empty-state text is absent, 7 day labels render, and the hidden summary matches the
   expected per-day counts.
3. **Statuses:** a `CANCELLED` and a `REJECTED` appointment in the week are not counted.
4. **Range + pagination:** the week request uses `page_size=100` and Mon 00:00+08:00 → next Mon 00:00+08:00;
   with a full first page (`total` > 100) the second page is requested.
5. **Failure isolation:** a failed week request shows `role="alert"` and no false "No weekly appointment volume";
   the today list still renders. A failed today request still leaves the chart usable.

### 6. Docs / task record

- No durable contract changed (`docs/COUNSELOR_DASHBOARD.md` lists capabilities, not layout; the appointment
  range filters are already documented). Optionally add one sentence to `docs/APPOINTMENT_SCHEDULING.md`
  noting the dashboard's weekly card uses the same Manila->UTC range filters.
- Update `.ai/CURRENT_TASK.md`: `Status: ACTIVE`, objective, in/out scope, acceptance criteria, the
  "Contracts to preserve" table from below, and planned verification; finish with `COMPLETED` + exact results.

## Contracts to preserve

| Invariant / capability | Owning contract and code | Regression test |
|---|---|---|
| The hook still returns the complete day; only rendering is capped | `useCounselorDashboard.js:37-77`; `WelcomeBanner` 67-71 | new test: 7 items → banner "7", 5 rows |
| Manila-local day → UTC range boundaries | `docs/APPOINTMENT_SCHEDULING.md:106`; `manilaToday` | new test asserts week boundaries |
| First page is not the complete list; page through | `.ai/UI_CHANGE_SAFETY.md` §2; hook loop | new test asserts page 2 fetch |
| A failed source is an error, not an empty result | `.ai/UI_CHANGE_SAFETY.md` §4 | new test asserts the alert |
| Counselor sees only their own appointments | server scope, `repository.py:391-397` | unchanged; no client-side scoping added |
| Statuses and totals stay accurate | `AppointmentResponse.status` | new test: cancelled/rejected excluded from counts |
| Existing today list ordering and fields | `formatSchedule`, `modeLabel`, `StatusBadge` | unchanged code paths |

Intentional, user-authorized behavior changes: 5-row cap with footer, weekly volume now data-backed with the
center-average line removed, and the two cards relocated.

## Validation

```powershell
node --test frontend/tests/counselor-dashboard.test.cjs
npm test            # from frontend/
npm run build       # from frontend/
```

Manual (counselor account): dashboard with 0, ≤5, and >5 appointments today; a week with data and a week with
none; confirm the row order (Today's + Case distribution, then Volume + Availability update), 7 Mon–Sun labels,
and the "Showing 5 of N" footer.

Risk: **MEDIUM** (localized UI + client-side aggregation; no auth/data boundary). One read-only in-task review
against the table above; no new OpenAPI snapshot (no API change). Do not weaken or delete existing tests.

## Risks / notes

- Adds one paginated request per dashboard load; bounded by `page <= 20` like the today loader.
- An all-zero week shows a flat line rather than the empty state (intentional). Change to the empty state on
  `sum(myCases) === 0` if preferred.
- `Case distribution` remains an empty state; enabling it needs a case/concern data source that does not exist.
- `.ai/CURRENT_TASK.md` currently holds the previous session's record and must be replaced rather than appended.
