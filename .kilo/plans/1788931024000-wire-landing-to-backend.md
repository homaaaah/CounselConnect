# Wire the static landing page to the backend (plain JavaScript)

**Risk class:** MEDIUM (API/UI integration; no schema, auth-boundary, or backend change)
**Route:** `api-or-schema` (`docs/API_CONTRACT.md`, `.ai/NAMING_CONVENTIONS.md`) + affected frontend code.

## Goal

Make the static landing page's login and signup modals actually call the existing FastAPI backend, via a new plain-JavaScript module. The React/TSX tree (`src/**`) stays untouched — it remains the tested canonical app.

## Backend contract (verified in code)

- `POST /auth/login` — JSON `{identifier, password}`. One identifier: students use student number, staff use email (staff email takes precedence; `auth/service.py:67`). Returns `{user: {user_id,email,role_code,account_status,first_name,last_name}, csrf_token, idle_expires_at, absolute_expires_at}` and sets the HttpOnly `counselconnect_session` cookie. Errors: `INVALID_CREDENTIALS` (401), `ACCOUNT_NOT_LOGINABLE` (403); envelope `{error:{code,message,details}}`.
- `GET /accounts/campuses` / `GET /accounts/programs` — `{items:[{campus_id,campus_name,...}|{program_id,program_name,...}]}` (`accounts/router.py:100-112`).
- `POST /accounts/register/student-with-cor` — multipart FormData with `first_name, middle_name?, last_name, email, password (8-128), student_number, campus_id (int), program_id (int), year_level (int 1-10), section, file=COR PDF (<=10MB)`; 201 → `{user, profile, next_step}`. Error codes: `EMAIL_ALREADY_REGISTERED`, `STUDENT_NUMBER_ALREADY_REGISTERED`, `COR_MUST_BE_PDF`, `COR_INVALID_PDF`, `COR_TOO_LARGE` (`accounts/router.py:42-97`).
- Transport rules (mirror `frontend/src/services/apiClient.ts`): `BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"`; `credentials: "include"`; CSRF token held in memory only, sent as `X-CSRF-Token` on unsafe methods when present (login/register are public — no CSRF needed). Backend CORS allows origin `http://localhost:5173`.

## User decisions (confirmed)

1. Wire the static modals with a new plain-JS file; no TSX→JS conversion of the React tree.
2. Login field relabeled **"Student number or email"**.
3. Successful login shows "Signed in as {first} {last}." then redirects to `./homescreen.html` (~700 ms delay, mirroring `LoginPage.tsx:19`).
4. Move the five static files into `frontend/public/` so `vite build` emits them into `dist/` — without this the wired modals work only on the dev server and Capacitor `webDir: "dist"` stays broken (deploy-safety review finding). Dev URLs are unchanged (public/ is served at `/`).

## Steps

1. **`.ai/CURRENT_TASK.md`** — replace with a new ACTIVE entry for this task (objective, route, in/out scope, acceptance criteria, planned verification).
2. **Move static assets** `frontend/{login_modal.html, signup_modal.html, homescreen.html, homescreen.css, homescreen.js}` → `frontend/public/` (move, do not copy — no duplicates at `/`). All existing relative paths (`./login_modal.html` fetch, `./homescreen.css`, `./homescreen.js`) remain valid in dev and dist.
3. **Create `frontend/landing-api.js`** (at frontend root — NOT in `public/`; it must be Vite-processed for `import.meta.env`). Contents:
   - `BASE_URL`, error-envelope parsing (`ApiError`-equivalent), module-scoped `csrfToken`, and a `request()` function mirroring `apiClient.ts` (`credentials:"include"`, JSON content-type unless FormData, `X-CSRF-Token` when held, 204 → undefined, non-OK → throw parsed envelope with `NETWORK_ERROR` fallback message "Cannot reach the server. Is the backend running?").
   - The modal loader moved verbatim in spirit from index.html's inline script: `extractModal`, `loadModal`, and the open/close/switch/overlay-click wiring for `loginBtn`, `connectBtn`, `closeLoginModal`, `closeSignupModal`, `switchToSignup` (await `Promise.all` before wiring; early-return on fetch failure — keep this).
   - **Reference data:** on modal load, populate the signup campus/program `<select>`s from `/accounts/campuses` + `/accounts/programs` (`option value={id}`); on failure leave selects with a disabled "Unavailable" option and block submit with a clear message.
   - **COR input:** wire the hidden file input — show chosen filename in `.file-name-text`; client-side reject non-`.pdf` and >10 MB with the same messages `useRegistration.ts:117-128` uses.
   - **Login submit:** `POST /auth/login` `{identifier, password}`; success → show success message `Signed in as {first} {last}.`, then `window.location.assign("./homescreen.html")` after ~700 ms; failure → show envelope message in the modal's form-message area.
   - **Signup submit:** build the exact FormData contract above; 201 → show the backend `next_step` message and reset the form; error codes mapped to friendly text (same mapping as `useRegistration.ts:115-130`).
   - Password eye toggle (login modal): click toggles input `type` password/text.
   - Double-submit guard: disable the submit button while a request is in flight.
   - No `console.log` of payloads; COR file contents are never logged (privacy rule).
4. **Edit `frontend/index.html`:** delete the entire inline `<script>` block; keep the two slot divs; add `<script type="module" src="./landing-api.js"></script>` before `</body>`. Vite bundles it into `dist/assets/` with env substitution.
5. **Edit `frontend/public/login_modal.html`:** label → "Student number or email"; add `id`/`name` attributes and `autoComplete="username"` / `autoComplete="current-password"`; add `<div class="form-message" id="loginFormMessage"></div>` inside the card; remove `onsubmit="event.preventDefault();"` (JS now owns submit). Leave "Remember me", social buttons, and "Forgot Password?" as documented visual-only decorations (no backend endpoints; reset email is pending ADR-P09).
6. **Edit `frontend/public/signup_modal.html`:** add `id`/`name`/`required` attributes (password `minLength=8`, section `maxLength=50` to match the React form); replace hardcoded campus/program options with a single disabled placeholder option each (JS fills real values); year-level options 1–6 (match `RegisterPage.tsx:89`; backend allows 1–10); keep the COR privacy sentence; add `id="signupFormMessage"` message div; remove the inline `onsubmit`.
7. **Append to `frontend/src/index.css`** (authored section): `.form-message` with `.success` / `.error` variants and a small overflow-ellipsis rule for `.file-name-text`. Nothing else in the React CSS baseline changes.
8. **`.ai/CURRENT_TASK.md`** → COMPLETED with actual verification results and limitations.

## Explicitly out of scope

- Any change to `frontend/src/**` except the `index.css` append; React tests; backend code.
- `homescreen.js` stale-month-selection bug and the dead Emergency button (known review findings; homescreen is a redirect target now, so schedule fixes separately).
- Idle-expiry warning (FR-AUTH-03) — belongs to the React session layer.
- Doc edits (`docs/TEAM_SETUP_GUIDE.md` demo flow still describes React hash routes; docs are team-governed contracts — flag, don't edit).
- CSRF recovery on reload (`/auth/csrf`) — nothing on the static page needs unsafe methods after login (redirect loses memory CSRF by design; the HttpOnly cookie persists).

## Verification

1. `npm run build` — `dist/` must contain: `index.html` (script rewritten to `/assets/*.js`), `login_modal.html`, `signup_modal.html`, `homescreen.html/.css/.js` (copied from `public/`), and the CSS bundle. Grep the built `dist/index.html` to confirm no inline `initPage` remains.
2. `npm test` — all 16 existing tests still pass (React tree untouched).
3. Dev-server asset check: `npm run dev` then `curl` `/login_modal.html` (contains "Student number or email"), `/signup_modal.html` (placeholder selects), `/landing-api.js` (served), `/homescreen.html`.
4. Live flow (only if backend + MySQL are running; otherwise record as not run): backend up (`uvicorn app.main:app`), `npm run dev`; in the browser — register a student with a PDF via the signup modal (expect the `next_step` success message), then log in with the new student number (expect redirect to `homescreen.html`); also verify `INVALID_CREDENTIALS` shows the error message inline.
5. Record honestly which checks ran; never claim unrun checks passed.

## Acceptance criteria

- `index.html` has zero inline JS and one module script tag; both modals submit through `landing-api.js` to the real endpoints with the exact payloads above.
- Campus/program options come from the API (no hardcoded names); year options are 1–6; COR input enforces PDF/10 MB client-side and uploads via FormData `file`.
- Login success message + redirect to `./homescreen.html`; error messages render inline in both modals.
- `vite build` emits all five static files plus the bundled JS; existing tests pass.
- No React source, backend, or docs files change; `.ai/CURRENT_TASK.md` documents the task.
