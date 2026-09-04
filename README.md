# CounselConnect

A centralized guidance-counseling platform for the **University of Caloocan City Guidance and Counseling Office** — connecting Students, Guidance Staff, and Counselors for enrollment (COR) verification, appointment scheduling, real-time messaging, SOS triage, wellness resources, a bounded virtual guidance assistant, and counselor operations.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TailwindCSS, CapacitorJS wrapper (responsive web) |
| Backend | Python + FastAPI — ONE deployable **modular monolith** |
| Database | MySQL 8.4 LTS |
| ORM / driver | SQLAlchemy 2.0 + PyMySQL (sync) |
| Migrations | Alembic |

## Repository layout

```text
backend/    FastAPI modular monolith (see backend/app/modules/)
frontend/   React + Vite + Tailwind + Capacitor scaffold
contracts/  Generated OpenAPI snapshot (placeholder until endpoints exist)
docs/       READ-ONLY feature contracts and rules (source of truth)
.ai/        READ-ONLY agent/project context (source of truth)
```

## Source of truth (read these first)

1. `.ai/RULES.md` and `AGENTS.md` — hard boundaries (roles, COR privacy, expression-cue rules)
2. `.ai/ARCHITECTURE.md` — modular monolith, layering (`routes → schemas → services → repositories`)
3. `docs/` — one contract per feature (registration, appointments, messaging, SOS, wellness, assistant, CMS, dashboard, database, security, API, workflows)
4. `.ai/NAMING_CONVENTIONS.md` — API/DB/code naming
5. `CounselConnect_Initial_Database_v4.sql` — canonical baseline schema

## Roles

Only three roles exist: **STUDENT**, **GUIDANCE_STAFF** (assigned COR verification only), **COUNSELOR** (highest authority). There is no Administrator role.

## Pending decisions (do not implement ahead of approval)

ADR-P01 auth mechanism · P02 real-time transport · P03 SOS instrument/thresholds/retention · P04 appointment timing/cutoffs/reminders · P05 COR upload limits · P06 expression model · P07 manual publication rule · P08 assistant provider.

## Setup (skeleton stage)

**Backend** — from `backend/`:

```bash
python -m pip install -r requirements.txt
copy .env.example .env   # fill local DB credentials
uvicorn app.main:app --reload
```

**Frontend** — from `frontend/`:

```bash
npm install
npm run dev
```

**Database** — apply the approved baseline `CounselConnect_Initial_Database_v4.sql` to MySQL 8.4, or run `alembic upgrade head` once a baseline migration is added under `backend/migrations/versions/`.

## Development rules (summary)

- Backend layering: router (transport) → schema (validation) → service (authorization + business rules) → repository (persistence).
- Cross-module access goes through another module's **service**, never its repository or models.
- Never persist: COR file contents, facial images/frames/embeddings, expression history, assistant conversation history, mirrored article bodies.
- Timestamps stored as UTC; enum values are `SCREAMING_SNAKE_CASE`; JSON fields are `snake_case`.
