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

Keep this connection info (host/user/password) — you'll put it in `backend/.env` next. You do NOT need to create any tables by hand; step 3 loads the canonical schema file and then runs migrations.

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

Tables are created in two parts: the canonical v4.1 schema file is loaded first, then Alembic applies the post-baseline migrations. The Alembic baseline revision (`8f0f8c585641`) is intentionally empty — do not rely on `alembic upgrade head` alone, or you will hit `Failed to open the referenced table 'users'`.

From `backend/` (where step 2 left you; `alembic.ini` and `.env` must be found here):

```bash
# 1) Load the canonical v4.1 schema (note the ../ path to db/)
mysql -u your_mysql_user -p counselconnect < ../db/CounselConnect_Initial_Database_v4.1.sql

# 2) Apply the remaining migrations on top
alembic upgrade head

# 3) Seed the shared demo data
mysql -u your_mysql_user -p counselconnect < dev_seed.sql
```

On Windows PowerShell, `<` redirection is not supported — wrap step 1/3 in `cmd /c` or pipe the file, for example:

```powershell
cmd /c "mysql -u your_mysql_user -p counselconnect < ..\db\CounselConnect_Initial_Database_v4.1.sql"
```

`dev_seed.sql` inserts the shared demo data (2 campuses, 1 department, 2 programs, hero text, 3 FAQs, 1 announcement, 3 emergency contacts, the dev Counselor and Superadmin). Without it the landing page looks empty and the registration form has no programs to pick.

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

1. **Register** — http://localhost:5173 → *Register* → enter email + password and attach your current COR PDF → submit. Registration does **not** sign you in; it returns a one-time token for the inline steps.
2. **Confirm** — the confirmation step appears inline on the same form; review the extracted fields (read-only) and click **Confirm details** (sent in the `X-COR-Token` header). Success = "Account activated. You can now sign in with your email or student number."
   - A COR whose barcode is missing/unreadable, or whose details cannot be read, asks for a re-upload instead (Poppler/Tesseract required); rejecting/re-uploading also stays inline.
3. **Counselor view** — `#staff-login` with the seeded counselor `counselor@ucc.edu.ph` / `counselor-dev-2026` → **Users** lists students and their screening status (read-only; click **View** for the full profile).
4. **Superadmin view** — `#staff-login` with the seeded superadmin `superadmin@ucc.edu.ph` / `superadmin-dev-2026` → **Users** with a **Recover** action for non-active students.
   - Seeded staff come from `dev_seed.sql` (developer-created per ADR-005). Rotate these dev passwords before any real deployment.

## Common problems

| Symptom | Cause → Fix |
|---|---|
| `Access denied for user` on backend start or any DB call | Wrong MySQL user/password in `.env` → fix and **restart uvicorn** (`.env` is read only at startup) |
| Landing page empty (no hero/FAQs) | Seed not loaded → re-run step 3 (`dev_seed.sql`) |
| Registration form has no program options | Same seed issue as above |
| Login says "Incorrect identifier or password" | Wrong credentials, or the staff seed row is missing → re-run `dev_seed.sql` (adds `counselor@ucc.edu.ph` / `counselor-dev-2026` and `superadmin@ucc.edu.ph` / `superadmin-dev-2026`) |
| `SCREENING_UNAVAILABLE` / registration returns 503 | COR screening tooling missing → install Poppler (`pdftotext`, `pdftoppm`) and Tesseract OCR, or set `COUNSELCONNECT_PDFTOTEXT_PATH` / `COUNSELCONNECT_PDFTOPPM_PATH` / `COUNSELCONNECT_TESSERACT_PATH` in `.env`, then restart uvicorn |
| Unsafe action says "missing or invalid CSRF token" | Reload to recover the session-bound token; if the session expired, sign in again. Normal reloads now restore CSRF automatically before showing protected pages. |
| COR always requests resubmission | Install Tesseract/Poppler (above); a scanned/photo COR needs OCR. Open barcode must decode to the student number. |
| Frontend shows "Request failed" on everything | Backend not running → start it first (step 4), frontend depends on it |
| `alembic upgrade head` says access denied | MySQL user lacks privileges on the `counselconnect` DB → grant ALL on `counselconnect.*` to your user |
| `alembic upgrade head` fails with `(1824, "Failed to open the referenced table 'users'")` | The canonical schema was not loaded first (the Alembic baseline revision is a no-op) → run step 3 in order: load `db/CounselConnect_Initial_Database_v4.1.sql`, then `alembic upgrade head` |
| Weird route 404s after editing backend files | Rare reload hiccup → restart uvicorn |

## Automated checks

From `backend/`, `python -m pytest app/tests -q` runs database-free tests and skips MySQL tests unless `COUNSELCONNECT_TEST_DATABASE_URL` is explicitly supplied in the process environment. It does not read this test URL from `.env` or fall back to the application's database.

Use a test-only MySQL server/account and a URL with driver `mysql+pymysql` and database name `counselconnect_test`. For example, the URL shape is `mysql+pymysql://TEST_USER:URL_ENCODED_PASSWORD@localhost:3306/counselconnect_test?charset=utf8mb4`. Supply your credentials privately through the environment. The account must be able to create/drop the run's `counselconnect_test_<random UUID>` schema (a grant on `counselconnect_test%` is enough; no access to the `mysql` system schema is required). The fixture never drops a pre-existing schema and removes only the schema it created. It applies the canonical baseline and real session migration automatically; a MySQL CLI is not required. COR tests use temporary directories and disable SMTP.

From `frontend/`, run `npm test` for session/registration component regressions and `npm run build` for the Vite production compilation. After API changes, run `python scripts/export_openapi.py --check` from `backend/`.

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
- Frontend: http://localhost:5173 · Sign in: `#login` (student number or email) / `#staff-login` (staff email) · Seeded staff: `counselor@ucc.edu.ph` / `counselor-dev-2026`, `superadmin@ucc.edu.ph` / `superadmin-dev-2026` · Users directory: `#users`
- Repo: https://github.com/jekjek29/CounselConnect
