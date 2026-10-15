# Plan — Apply our work onto `CurrentMainVersion/`

Status: READY FOR APPROVAL
Source: `CounselConnectDev/` (our working tree — automated COR screening work, ADR-029/030)
Target: `CounselConnectDev/CurrentMainVersion/` (current main snapshot; no `.git`, old `enrollment_verification` wiring)
Method (approved): **delta copy — keep any CurrentMainVersion-only files**
Risk: MEDIUM (bulk file copy; code verified afterward). Must run from a Code agent (copying + tests are writes).

## Context (verified)

- Ours is a **superset** of `CurrentMainVersion`:
  - ours has `backend/app/modules/cor_screening/`; CurrentMainVersion does not (it has `enrollment_verification`).
  - ours keeps `assistant/` + `wellness_resources/` and both are routed; only `enrollment_verification` routing was replaced by `cor_screening`.
  - ours has 3 extra migrations (`20260930_automated_cor_screening`, `20260930_extracted_validity`, `20260930_superadmin_role`); CurrentMainVersion stops at `20260916_scheduled_appointment_chat`.
  - ours has the newer docs (incl. the earlier MergeMD-merged docs + AUDIO_VIDEO/Counseling/Clinical docs); CurrentMainVersion's docs are the older 20-file set.
- `CurrentMainVersion` is **not** a git repo (no `.git`), so this is a file apply, not a git merge (history is not preserved).

## Steps (Code agent)

1. **Dry run / manifest**: walk `SOURCE=CounselConnectDev`, `TARGET=CounselConnectDev/CurrentMainVersion`; for each file compute SHA-256; classify `new`, `differs`, `same`; also list `target-only` files. Print counts and the `new`/`differs` lists. No writes.
2. **Pre-checks**:
   - Diff `backend/requirements.txt` (ours vs target) — confirm ours only adds `zxing-cpp`/`Pillow`; if target has deps we lack, stop and report.
   - Confirm no secrets are in scope (`.env`, `backend/.env`) — they must be excluded.
3. **Apply delta copy** (overwrite only `new` + `differs`; do not delete anything):
   - Copy source → target for every `new`/`differs` file.
   - Excluded directories (never walked): `.git`, `.venv`, `node_modules`, `dist`, `__pycache__`, `.pytest_cache`, `var`, `backend/var`, `.kilo`, `.vscode`, and `CurrentMainVersion` itself.
   - Excluded files: any `.env` (`*/.env`), `backend/.env*`, DB dumps, `*.log`.
   - Print a manifest of every copied file.
4. **Sanity in the target** (run from `CurrentMainVersion/backend` with our venv or a fresh one):
   - `python -c "import app.main; print('import-ok')"`.
   - `pytest app/tests -q` → expect ~80 passed, ~120 skipped.
   - `python scripts/export_openapi.py --check` → passes (ours `contracts/openapi.json` copied).
5. **Frontend in the target** (`CurrentMainVersion/frontend`):
   - `npm install` (if needed) → `npm test` (expect ~67 pass / 2 known calendar date-rot fails) → `npm run build`.
6. **Migration graph check**: from `CurrentMainVersion/backend`, `alembic heads` → single head `20260930_superadmin_role`; `alembic history` is linear from `8f0f8c585641`.
7. **Report**: total copied, manifest, verification results, and any `target-only` files left in place.

## Expected high-impact copies

- `backend/app/modules/cor_screening/**` (new), `backend/app/modules_router.py` (cor_screening in, enrollment_verification out of routing), `backend/app/db/base.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/modules/auth/service.py`, `backend/app/modules/accounts/**`.
- `backend/migrations/versions/20260930_*` (3 new), `backend/requirements.txt`, `backend/dev_seed.sql`.
- `contracts/openapi.json`.
- `frontend/**` (register/confirm/reject, cor screening, Users directory, notifications, `index.css`, hooks) and `frontend/tests/**`.
- `.ai/{DECISIONS,CURRENT_TASK,NAMING_CONVENTIONS,CONTEXT_MAP}.md`, `AGENTS.md`, `README.md`, `docs/**` (our newer set), `Merged/…` docs already in ours.

## Risks & notes

- **No history**: `CurrentMainVersion` gets files only. If a real PR/merge is needed later, re-clone main and merge the branch instead.
- **Kept target-only files**: preserved by request. Verify the app still imports/routes (step 4). If a target-only file conflicts (e.g., an extra router), reconcile manually.
- **`contracts/openapi.json`**: only ours is valid after the copy — regenerate if backend changes.
- **Docs inconsistency (pre-existing)**: our docs mix ADR-029/030 (implemented) with MergeMD's ADR-036 target (no Guidance Staff / no Wellness). This plan copies ours as-is; reconciling the target is a separate task.
- **Nested folder**: `CurrentMainVersion/` sits inside our repo and must never be committed (`git add -A` would otherwise include it). Consider moving it out of the repo after the copy.
- **Secrets/data**: `.env` and `backend/var/` are excluded; do not copy COR files.

## Open items (confirm during execution)

- After the copy, do you want `CurrentMainVersion` (a) kept as the deliverable to push, (b) swapped in to replace `CounselConnectDev`, or (c) deleted? Recommend (a) then delete/ignore it in the parent repo.
- Should `design/DFD_*` / `design/ERD_*` also be copied if they differ? (Ours-only currently; default: copy ours.)
