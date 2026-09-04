# CounselConnect — Teammate Setup Guide

Everything needed to run the full stack on your own machine: backend (FastAPI + MySQL), frontend (React + Vite), database, seed data, and the working demo flow. Follow top to bottom; each step says exactly what success looks like.

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
COUNNELCONNECT_DB_NAME=counselconnect
COUNSELCONNECT_DB_USER=your_mysql_user
COUNSELCONNECT_DB_PASSWORD=your_mysql_password

COUNSELCONNECT_DEV_ADMIN_KEY=dev-review-key-2026
```

> ⚠️ Fix the typo above when editing: `COUNSELCONNECT_DB_NAME` (double S in CONNECT). 

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
2. **Review** — http://localhost:5173/#review → enter key `dev-review-key-2026` → your application appears under *Pending* → click the applicant to see details and the PDF preview → **Approve**.
   - On a fresh database the first registered student is `user_id 1` — approve/reject need that user to exist, and this is why: the dev flow records reviewer id 1.
3. **Check result** — *All applications* tab shows `APPROVED` with validity date; your inbox (if SMTP configured) has the decision email.

## Common problems

| Symptom | Cause → Fix |
|---|---|
| `Access denied for user` on backend start or any DB call | Wrong MySQL user/password in `.env` → fix and **restart uvicorn** (`.env` is read only at startup) |
| Landing page empty (no hero/FAQs) | Seed not loaded → re-run step 3 (`dev_seed.sql`) |
| Registration form has no program options | Same seed issue as above |
| Reviewer page says "Reviewer access is disabled" (503) | `COUNSELCONNECT_DEV_ADMIN_KEY` missing/blank in `.env` → add it, restart uvicorn |
| Reviewer page says "wrong key" | Key in `.env` doesn't match the key entered in the UI → both must be `dev-review-key-2026` (or your own value, matched) |
| Toast says "email NOT sent (SMTP not configured)" | Expected when SMTP vars are blank — fill them or ignore |
| Approved but nothing arrives in email | Gmail rejected the app password → confirm it's a fresh App Password (not your login password), 2FA is on, and restart uvicorn |
| Frontend shows "Request failed" on everything | Backend not running → start it first (step 4), frontend depends on it |
| `alembic upgrade head` says access denied | MySQL user lacks privileges on the `counselconnect` DB → grant ALL on `counselconnect.*` to your user |
| Weird route 404s after editing backend files | Rare reload hiccup → restart uvicorn |

## Rules everyone must follow

- **Never commit `.env`** — Git already blocks it via `.gitignore`; if `git status` shows it, something is wrong, stop and ask in the team chat.
- **Never commit anything under `backend/var/`** — that folder holds real applicant COR PDFs (private data). It is ignored too.
- Pull before you start working, commit small, push often: `git add -A` → `git commit -m "short message"` → `git push`.
- `docs/` and `.ai/` are read-only contracts (the "source of truth"). Do not edit them casually — changes go through the team.
- Login is intentionally a placeholder (the team hasn't approved the auth mechanism, ADR-P01). Don't build auth ahead of that decision.
- Don't share the repo link publicly; it's a private capstone repo.

## Quick reference

- Backend: http://localhost:8000 · API docs: http://localhost:8000/docs · Health: `/api/v1/health`
- Frontend: http://localhost:5173 · Reviewer console: `#review` (key: `dev-review-key-2026`)
- Repo: https://github.com/jekjek29/CounselConnect
