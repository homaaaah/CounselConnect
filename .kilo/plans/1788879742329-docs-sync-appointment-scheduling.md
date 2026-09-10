# Plan: Sync all MD docs to latest merged GitHub state (main @ 7e38a37)

## Context (verified)

- `main` == `origin/main` at `7e38a37`: includes "Implement appointment scheduling and separate student/staff login forms" (`35569ce`) and new `.ai/CONTRIBUTING.md` (`6b35747`/PR #2).
- TypeScript→JavaScript migration exists ONLY on unmerged branches (`origin/frontend/migrate-to-javascript`, `origin/docs/javascript-stack-wording`). All `main` docs must stay TypeScript. Do NOT apply JS wording.
- `.ai/PROJECT.md` is corrupted: since commit `98fe335` it contains a duplicate of Naming Conventions. The original Project Context (recoverable via `git show 7a1925e:.ai/PROJECT.md`) is still accurate.
- The newer ADR-019/session naming content stranded in that duplicate must be folded into `.ai/NAMING_CONVENTIONS.md` (user decision: Restore + fold).
- `alembic upgrade head` alone cannot create tables: baseline revision `8f0f8c585641` is a verified no-op; `297c92da239d` adds `user_sessions` and would fail on an empty DB. Real setup = apply `db/CounselConnect_Initial_Database_v4.1.sql` (21 tables) → stamp `8f0f8c585641` → upgrade (22 tables) → seed.
- `docs/API_CONTRACT.md` cites pending ADR-P09, but `.ai/DECISIONS.md` has no P09 row (user decision: register it).
- Messaging service (`backend/app/modules/messaging/service.py:32`) validates linkage and closes a linked conversation on authorized terminal outcomes; it does not create/open conversations.
- Verified current, NO changes: `AGENTS.md`, `.kilo/rules/*`, `.ai/RULES.md`, `CONTEXT_MAP.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, all `docs/` feature docs except those listed below, `backend/README.md`, `backend/app/README.md`, `backend/app/modules/README.md`, `frontend/README.md`, `frontend/src/features/README.md`, `docs/README.md`, `docs/structure/*`, `design/*`. Do not bulk-rewrite (MARKDOWN_UPDATE_GUIDE rule).
- Risk class: MEDIUM (documentation contracts; no code changes).

## Files to change (7 + task file), in batches

### Batch 1 — Task bookkeeping
1. `.ai/CURRENT_TASK.md`: replace stale content. `Status: ACTIVE`, objective "sync all MD docs to main @ 7e38a37", route `project` + affected docs, in-scope list below, acceptance = all batches below, verification = Batch 6 checks. (Mark COMPLETED at the end.)

### Batch 2 — `.ai/` context files
2. `.ai/PROJECT.md`: replace entire content with the restored Project Context from `git show 7a1925e:.ai/PROJECT.md` (client, goal, team, users, architecture, stack, feature-ownership table, stable scope, pointer to DECISIONS).
3. `.ai/NAMING_CONVENTIONS.md`: fold in the newer content currently stranded in the PROJECT.md duplicate:
   - Canonical table: add rows `| Authenticated user session | user_sessions, session |` and `| Counselor SOS availability | AVAILABLE, BUSY, UNAVAILABLE |`.
   - Database section: add bullet "Use `user_sessions` for revocable authentication sessions, with `session_id`, `token_hash`, `csrf_token_hash` when server-held, `last_activity_at`, `absolute_expires_at`, and `revoked_at`. Never name or store a raw session token as an identifier."
   - Replace auth-routes line with: "Auth action exceptions use `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/csrf`, and explicit password-recovery actions. Do not add `/auth/refresh` unless a future approved token design requires it." (matches implemented `auth/router.py`).
   - Approved-states table: add `| Counselor SOS availability | AVAILABLE, BUSY, UNAVAILABLE |`.
4. `.ai/README.md`: add table row `| CONTRIBUTING.md | Git/GitHub team workflow (branch-per-task, PR review) |`.
5. `.ai/DECISIONS.md`: add Pending row `| ADR-P09 | Capacitor session-credential transport and production password-reset email delivery/fallback. |`.

### Batch 3 — Root README.md
6. `README.md`:
   - `contracts/` layout line → "Generated OpenAPI snapshot of implemented endpoints (regenerate via `python scripts/export_openapi.py`; never hand-edit)".
   - Pending decisions line: drop `ADR-P01` (approved as ADR-019), keep P02–P08, add P09 → "ADR-P02 real-time transport · P03 SOS instrument/thresholds/retention · P04 appointment timing/cutoffs/reminders/blocked periods · P05 COR upload limits · P06 expression model · P07 manual publication rule and attachment limits · P08 assistant provider · P09 Capacitor credential transport and reset-email delivery".
   - Heading `## Setup (skeleton stage)` → `## Local setup`.
   - Development rules: add "- Team Git workflow: one branch per task, PR review before merge (`.ai/CONTRIBUTING.md`); never push directly to `main`."

### Batch 4 — docs/TEAM_SETUP_GUIDE.md
7. Fix database setup (currently broken step 3):
   - Step 1 sentence "You do NOT need to create any tables by hand; migrations do that" → the approved baseline SQL creates all tables; alembic only adds later migrations.
   - Step 3 commands (run from `backend/`):
     ```bash
     mysql -u your_mysql_user -p < ..\db\CounselConnect_Initial_Database_v4.1.sql
     alembic stamp 8f0f8c585641
     alembic upgrade head     # adds user_sessions → 22 tables total
     mysql -u your_mysql_user -p counselconnect < dev_seed.sql
     ```
     (Mac/Linux path `../db/...`; the baseline SQL creates the DB itself if step 1 was skipped.)
   - Login wording: note the separate student (student number) vs staff (email) sign-in forms; the demo counselor uses the staff form.
   - Demo flow: add brief step 4 "Appointments (optional, ~3 min)": counselor signs in → `#appointments` → creates availability (campus, date, time range, duration, mode) → student signs in → `#appointments` → requests a slot → request shows `PENDING`; counselor confirms/rejects.
   - Rules section: replace the "git add -A → commit → push" bullet with the `.ai/CONTRIBUTING.md` branch/PR workflow (never work or push directly on `main`).
   - Quick reference: add `#appointments` (Appointments console).

### Batch 5 — docs/REAL_TIME_MESSAGING.md
8. Under "Appointment-linked conversations" add an implemented-status bullet: "Implemented status: the messaging service validates participant/mode/type linkage for an already-linked conversation and closes it when the appointments service reports an authorized terminal outcome; it does not create or open conversations — that awaits the Live Chat transport decision (ADR-P02)." Keep all existing contract bullets as requirements.

### Batch 6 — Verify and finalize
9. Verification (run all, no claims without running):
   - `git status` + `git diff --name-only` → exactly: `.ai/CURRENT_TASK.md`, `.ai/PROJECT.md`, `.ai/NAMING_CONVENTIONS.md`, `.ai/README.md`, `.ai/DECISIONS.md`, `README.md`, `docs/TEAM_SETUP_GUIDE.md`, `docs/REAL_TIME_MESSAGING.md`.
   - Re-read each diff; confirm restored PROJECT.md matches `git show 7a1925e:.ai/PROJECT.md`; NAMING_CONVENTIONS gains every stranded item; setup-guide commands match `backend/migrations/versions/` reality (stamp id `8f0f8c585641`, upgrade adds `user_sessions`).
   - Cross-check: every referenced path exists (`db/CounselConnect_Initial_Database_v4.1.sql`, `.ai/CONTRIBUTING.md`, `backend/dev_seed.sql`); no doc claims JS stack; P01 absent from pending lists; P09 present in DECISIONS + root README + (existing) API_CONTRACT.
   - Markdown table/link sanity on all 8 files.
   - Mark `.ai/CURRENT_TASK.md` `Status: COMPLETED` with actual verification results.

## Out of scope
- JavaScript-migration wording (unmerged branches only).
- `contracts/openapi.json` (generated; regenerate only, never hand-edit).
- `docs/MARKDOWN_UPDATE_GUIDE.txt` (not MD; its triggers are respected, not rewritten).
- Any code, schema, or OpenAPI change. No commits/pushes (AI needs explicit developer approval per `.ai/CONTRIBUTING.md`; this plan's executor should leave changes uncommitted for developer review).
