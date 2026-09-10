# Merge `counselconnect-frontend/` copy into the main repo

**Risk class:** MEDIUM (replaces the served frontend entry page; presentation only — no data, security, or business logic)

## Context

- `counselconnect-frontend/` is a plain-folder snapshot (no `.git`) of the repo after two working sessions that main does not have:
  1. **Capstone landing session** (basis: `Capstone-Project-Documentation.docx`): static marketing `frontend/index.html` + full stylesheet in `frontend/src/index.css`.
  2. **Modal-split session** (basis: copy's `.ai/CURRENT_TASK.md`, 2026-09-08): `login_modal.html` + `signup_modal.html` loaded by fetch+DOMParser from `index.html`.
  3. **Undocumented extra** (user approved inclusion): `homescreen.html/css/js` — standalone "UniCounsel" schedule-page prototype.
- Everything else in the copy is either **byte-identical to main** (backend, contracts, db, design, docs except 2, all React `src/` code, tests, configs) or **stale** (`.ai/*`, root `README.md`, `docs/TEAM_SETUP_GUIDE.md`, `docs/REAL_TIME_MESSAGING.md`, `package-lock.json` — main's 2026-09-09 docs-sync state is newer and must be kept).
- A verified full diff was performed (file-by-file, node_modules/.git/.venv/env excluded). Only the 7 files below need action.

## User decisions (already confirmed)

1. Merge the landing page exactly as the copy has it (React SPA becomes unserved at `/` — the docx documents this as a known limitation; porting the design into React components is the agreed next step).
2. Include the undocumented `homescreen.*` prototype files.
3. Keep the `counselconnect-frontend/` copy folder in place after the merge (manual cleanup later).

## Actions (all via Read + Write file tools with absolute paths)

**Copy content verbatim from the copy tree into the main tree** (read source, write to destination with identical content; do not reformat, do not "fix" anything):

| # | Source (read) | Destination (write) | Nature |
|---|---|---|---|
| 1 | `counselconnect-frontend\frontend\index.html` (321 lines) | `frontend\index.html` | **Overwrite** main's 12-line Vite React entry |
| 2 | `counselconnect-frontend\frontend\src\index.css` (738 lines) | `frontend\src\index.css` | **Overwrite** main's 3-line Tailwind-only file (Tailwind `@tailwind` directives are retained at top of copy's file) |
| 3 | `counselconnect-frontend\frontend\login_modal.html` (60 lines) | `frontend\login_modal.html` | New file |
| 4 | `counselconnect-frontend\frontend\signup_modal.html` (103 lines) | `frontend\signup_modal.html` | New file |
| 5 | `counselconnect-frontend\frontend\homescreen.html` (165 lines) | `frontend\homescreen.html` | New file |
| 6 | `counselconnect-frontend\frontend\homescreen.css` (519 lines) | `frontend\homescreen.css` | New file |
| 7 | `counselconnect-frontend\frontend\homescreen.js` (164 lines) | `frontend\homescreen.js` | New file |

**Workflow bookkeeping (required by `.kilo/rules/01-workflow.md`):**

8. Before writing code files: replace main's `.ai/CURRENT_TASK.md` with a new ACTIVE entry for this merge task (objective, route `project`, in/out scope, acceptance criteria, planned verification, risk class MEDIUM).
9. After verification: set the same file to `Status: COMPLETED` with actual verification results, remaining limitations, and note that `homescreen.*` is an undocumented prototype pending documentation.

## Explicitly NOT changed (stale in the copy — keep main's newer versions)

- `.ai/*` (all: PROJECT.md restored version, NAMING_CONVENTIONS, DECISIONS with ADR-P09, README with CONTRIBUTING row, CONTRIBUTING.md, plus ARCHITECTURE/CONTEXT_MAP/REQUIREMENTS/RULES identical anyway) — except CURRENT_TASK.md which gets the new task entry per action 8–9.
- Root `README.md`, `docs/TEAM_SETUP_GUIDE.md`, `docs/REAL_TIME_MESSAGING.md`, `.kilo/plans/*` (main's 2026-09-09 docs-sync output).
- `frontend/package-lock.json` (main's is newer npm output; same 281-package tree, `package.json` identical → no reinstall needed).
- `backend/`, `contracts/`, `db/`, `design/` (byte-identical).
- All React code: `frontend/src/**` except `src/index.css` (action 2), `frontend/tests/**`, all configs (`package.json`, `tsconfig.json`, `vite.config.ts`, `tailwind.config.js`, `postcss.config.js`, `capacitor.config.ts`, `.env.example`, `.gitignore`, `README.md`).
- Do NOT copy `frontend/tsconfig.tsbuildinfo` from the copy (build artifact, gitignored via `*.tsbuildinfo`).
- Do NOT delete the `counselconnect-frontend/` folder (user decision).
- No backend, database, security, or role logic is touched.

## Execution constraints (environment-specific)

- Bash/shell is effectively unusable for this work: the workspace path contains `[1]` which PowerShell treats as a wildcard (workdir silently fails → commands run from System32), and permission rules block `cp`, `mv`, `New-Item`, `Test-Path`, `npm`, and all non-read-only `git` subcommands. **Use only Read/Write/Edit/Glob/Grep tools with absolute paths.**
- Read-only git (`git status`, `git diff`) is allow-listed but only runs in System32 (wrong dir) — do not rely on it; verify via file reads instead.

## Verification plan

1. **Content fidelity:** after each write, re-read the destination file and line-count + spot-check (head/middle/tail) against the source in the copy; all 7 must match exactly.
2. **No scope creep:** glob/read to confirm no other files under `frontend/`, `.ai/`, `docs/`, `backend/` were modified (only CURRENT_TASK.md plus the 7 files above differ).
3. **Build/tests (attempt, with fallback):** try `npm run build` and `npm test` in `frontend/`. If the permission system blocks them (likely), do NOT claim they passed — record "blocked in session" in CURRENT_TASK.md and ask the user to run `npm run build` and `npm test` in `frontend/` manually and report results. Note: the docx records `npm run build` PASSING with exactly this index.html/index.css state, so breakage is not expected.
4. **MEDIUM-risk in-task review:** after verification, re-read the final state of the 7 files plus CURRENT_TASK.md against this plan's acceptance criteria (exact-copy fidelity; exclusions respected) and fix any confirmed deviation.

## Known limitations to carry into CURRENT_TASK.md

- The landing `index.html` no longer loads `src/main.tsx`, so the React SPA (login/register/appointments/reviewer pages) is not reachable from `/` on the dev server until the design is ported into React components (agreed next step; see docx section 6).
- Modal partials and `homescreen.html` load via `fetch` — works on the Vite dev server only; a default `vite build` does not copy extra root `.html` partials into `dist`, so the built app will not show modals until the React port.
- `file://` double-click of `index.html` loads the page styled (relative `./src/index.css`) but cannot fetch the modal partials; use `npm run dev`.
- `homescreen.*` is not yet documented in `.ai/` — flag it in CURRENT_TASK.md as a pending documentation item.
- Forms are `preventDefault()` stubs; no backend wiring (unchanged from the copy sessions).

## Acceptance criteria

- The 7 listed files in main exactly match their copy counterparts (verified by re-read comparison).
- Main's `.ai/` docs (other than CURRENT_TASK.md), root README, docs/, package-lock.json, backend/, contracts/, db/, design/, and all React src/tests/configs are untouched by the merge.
- `.ai/CURRENT_TASK.md` reflects this task as COMPLETED with actual verification results and the limitations above.
- No claim is made that build/tests passed unless they actually ran.
