# CounselConnect

A centralized guidance-counseling platform for the **University of Caloocan City Guidance and Counseling Office** — connecting Students, Guidance Staff, and Counselors for enrollment (COR) verification, appointment scheduling, real-time messaging, SOS triage, wellness resources, a bounded virtual guidance assistant, and counselor operations.

## Stack

| Layer | Technology |
|---|---|
| Frontend | JavaScript (React) + Vite + TailwindCSS, CapacitorJS wrapper (responsive web) |
| Backend | Python + FastAPI — ONE deployable **modular monolith** |
| Database | MySQL 8.4 LTS |
| ORM / driver | SQLAlchemy 2.0 + PyMySQL (sync) |
| Migrations | Alembic |

## Repository layout

```text
backend/    FastAPI modular monolith (see backend/app/modules/)
frontend/   JavaScript (React) + Vite + Tailwind + Capacitor scaffold
contracts/  Generated OpenAPI snapshot (placeholder until endpoints exist)
docs/       READ-ONLY feature contracts and rules (source of truth)
db/         Approved baseline SQL schemas (v4 design, v4.1 MySQL-8.4 baseline)
design/     AI-readable design exports (DFD, ERD, Flowchart)
.ai/        READ-ONLY agent/project context (source of truth)
```

## Source of truth (read these first)

1. `.ai/RULES.md` and `AGENTS.md` — hard boundaries (roles, COR privacy, expression-cue rules)
2. `.ai/ARCHITECTURE.md` — modular monolith, layering (`routes → schemas → services → repositories`)
3. `docs/` — one contract per feature (registration, appointments, messaging, SOS, wellness, assistant, CMS, dashboard, database, security, API, workflows)
4. `.ai/NAMING_CONVENTIONS.md` — API/DB/code naming
5. `db/CounselConnect_Initial_Database_v4.1.sql` — canonical baseline schema (v4 design preserved as `v4.sql`)

## Roles

Four roles exist: **STUDENT**, **GUIDANCE_STAFF** (no COR duty — verification is automated, ADR-029), **COUNSELOR** (highest authority for counseling operations), and **SUPERADMIN** (narrow account-recovery/operational-exceptions role; never approves a COR, ADR-030).

## Pending decisions (do not implement ahead of approval)

The original pending decisions (ADR-P01–P08) are all resolved — see `.ai/DECISIONS.md` (ADR-019–ADR-027). Known limits still open: COR **image** support, authoritative registrar/barcode verification, production private-storage provider, and finalized COR thresholds/retention (see ADR-029).

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

**Database** — apply the approved baseline `db/CounselConnect_Initial_Database_v4.1.sql` to MySQL 8.4 (see `docs/TEAM_SETUP_GUIDE.md` for the full walkthrough), or run `alembic upgrade head` from `backend/` after the baseline is stamped.

## Development rules (summary)

- Backend layering: router (transport) → schema (validation) → service (authorization + business rules) → repository (persistence).
- Cross-module access goes through another module's **service**, never its repository or models.
- Never persist: COR file contents, facial images/frames/embeddings, expression history, assistant conversation history, mirrored article bodies.
- Timestamps stored as UTC; enum values are `SCREAMING_SNAKE_CASE`; JSON fields are `snake_case`.
