# CounselConnect — Teammate Setup Guide

Everything needed to run the full stack on your own machine: backend (FastAPI + MySQL), frontend (JavaScript/React + Vite), database, seed data, and the working demo flow. Follow top to bottom; each step says exactly what success looks like.

## What you need installed first

| Tool | Version we use | Check with |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ (we use 24) | `node --version` |
| MySQL | 8.4 LTS (server running locally) | MySQL Workbench / `mysql` client connects |
| Git | any recent | `git --version` |

## 0. Get the code

```bash
git clone https://github.com/jekjek29/CounselConnect.git
cd CounselConnect
```

If you get a 404: you haven't accepted the repo invite yet — check the email from GitHub or your GitHub notifications, then retry.

## 1. Create the database (once)

Connect to your local MySQL as any admin user and run:

```sql
CREATE DATABASE counselconnect CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

Keep this connection info (host/user/password) — you'll put it in `backend/.env` next. You do NOT need to create any tables by hand; migrations do that.

## 2. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env
```

Open `backend\.env` and fill in **your own** values:

```env
COUNSELCONNECT_DB_HOST=localhost
COUNSELCONNECT_DB_PORT=3306
COUNSELCONNECT_DB_NAME=counselconnect
COUNSELCONNECT_DB_USER=your_mysql_user
COUNSELCONNECT_DB_PASSWORD=your_mysql_password
```

Optional (real emails; without it, decisions report "email not sent" honestly):
```env
COUNSELCONNECT_SMTP_USER=your-gmail@gmail.com
COUNSELCONNECT_SMTP_PASSWORD=your-16-char-gmail-app-password
```
The Gmail app password is NOT your normal password — create one at myaccount.google.com → Security → 2-Step Verification → App passwords.

## 3. Create tables + seed data

```bash
alembic upgrade head     # creates all 21 tables
mysql -u your_mysql_user -p counselconnect < dev_seed.sql
```

`dev_seed.sql` inserts the shared demo data (2 campuses, 1 department, 2 programs, hero text, 3 FAQs, 1 announcement, 3 emergency contacts). Without it the landing page looks empty and the registration form has no programs to pick.

## 4. Start the backend

```bash
uvicorn app.main:app --reload
```

Success = it prints `Uvicorn running on http://127.0.0.1:8000` and http://localhost:8000/api/v1/health returns `{"status":"ok"}` (docs at http://localhost:8000/docs).

## 5. Frontend setup

In a **second terminal** (keep the backend running):

```bash
cd frontend
npm install
copy .env.example .env      # Mac/Linux: cp .env.example .env
npm run dev
```

Success = http://localhost:5173 shows the CounselConnect landing page with the hero text, FAQs, and announcement from the seed data.

## 6. Demo flow to verify your setup (5 minutes)

1. **Register** — http://localhost:5173 → *Register* → fill the form, pick a program, attach any PDF (fake is fine, e.g. rename a blank `test.pdf`) → submit. Success = confirmation message.
2. **Review** — http://localhost:5173/#login → sign in as the seeded counselor: email `counselor@ucc.edu.ph`, password `counselor-dev-2026` → go to `#review` → your application appears under *Pending* → click the applicant to see details and the PDF preview → **Approve**.
   - The counselor account comes from `dev_seed.sql` (developer-created per ADR-005). Rotate this password before any real deployment.
3. **Check result** — *All applications* tab shows `APPROVED` with validity date; your inbox (if SMTP configured) has the decision email.

## Common problems

| Symptom | Cause → Fix |
|---|---|
| `Access denied for user` on backend start or any DB call | Wrong MySQL user/password in `.env` → fix and **restart uvicorn** (`.env` is read only at startup) |
| Landing page empty (no hero/FAQs) | Seed not loaded → re-run step 3 (`dev_seed.sql`) |
| Registration form has no program options | Same seed issue as above |
| Login says "Incorrect identifier or password" | Wrong credentials, or the counselor seed row is missing → re-run `dev_seed.sql` (it adds `counselor@ucc.edu.ph` / `counselor-dev-2026`) |
| Reviewer page says "Only a Guidance Counselor may perform this action" (403) | You signed in as a student account → sign in with the counselor account |
| Unsafe action says "missing or invalid CSRF token" | Reload to recover the session-bound token; if the session expired, sign in again. Normal reloads now restore CSRF automatically before showing the reviewer. |
| Toast says "email NOT sent (SMTP not configured)" | Expected when SMTP vars are blank — fill them or ignore |
| Approved but nothing arrives in email | Gmail rejected the app password → confirm it's a fresh App Password (not your login password), 2FA is on, and restart uvicorn |
| Frontend shows "Request failed" on everything | Backend not running → start it first (step 4), frontend depends on it |
| `alembic upgrade head` says access denied | MySQL user lacks privileges on the `counselconnect` DB → grant ALL on `counselconnect.*` to your user |
| Weird route 404s after editing backend files | Rare reload hiccup → restart uvicorn |

## Automated checks

From `backend/`, `python -m pytest app/tests -q` runs database-free tests and skips MySQL tests unless `COUNSELCONNECT_TEST_DATABASE_URL` is explicitly supplied in the process environment. It does not read this test URL from `.env` or fall back to the application's database.

Use a test-only MySQL server/account and a URL with driver `mysql+pymysql` and database name `counselconnect_test`. For example, the URL shape is `mysql+pymysql://TEST_USER:URL_ENCODED_PASSWORD@localhost:3306/counselconnect_test?charset=utf8mb4`. Supply your credentials privately through the environment. The account must be able to create/drop the run's `counselconnect_test_<random UUID>` schema. The fixture never drops a pre-existing schema and removes only the schema it created. It applies the canonical baseline and real session migration automatically; a MySQL CLI is not required. COR tests use temporary directories and disable SMTP.

From `frontend/`, run `npm test` for session/reviewer component regressions and `npm run build` for the Vite production compilation. With Node and frontend dependencies installed, the backend suite also exercises the actual React app against a temporary loopback FastAPI server and the isolated test schema (login, reload, approval, logout). This is an HTTP/component integration check, not a full browser test. After API changes, run `python scripts/export_openapi.py --check` from `backend/`.

The backend automatically runs COR expiry/deletion retries while serving requests. See `REGISTRATION_VERIFICATION.md` for cleanup monitoring and one-shot scheduling when the application is offline.

## Rules everyone must follow

- **Never commit `.env`** — Git already blocks it via `.gitignore`; if `git status` shows it, something is wrong, stop and ask in the team chat.
- **Never commit anything under `backend/var/`** — that folder holds real applicant COR PDFs (private data). It is ignored too.
- Pull before you start working, commit small, push often: `git add -A` → `git commit -m "short message"` → `git push`.
- `docs/` and `.ai/` are read-only contracts (the "source of truth"). Do not edit them casually — changes go through the team.
- Auth is ADR-019 (opaque HttpOnly session cookie + CSRF + Argon2id). The dev counselor password must be rotated before any real deployment.
- Don't share the repo link publicly; it's a private capstone repo.

## Quick reference

- Backend: http://localhost:8000 · API docs: http://localhost:8000/docs · Health: `/api/v1/health`
- Frontend: http://localhost:5173 · Sign in: `#login` (counselor: `counselor@ucc.edu.ph` / `counselor-dev-2026`) · Reviewer console: `#review`
- Repo: https://github.com/jekjek29/CounselConnect
