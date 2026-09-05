# CounselConnect — Current Task

**Status:** COMPLETED
**Risk class:** MEDIUM (structural file moves + reference updates; no code logic change)

## Objective

Reorganize the cluttered repository root while keeping every functional path working: SQL baselines into `db/`, large AI-readable design exports (DFD/ERD/Flowchart) into `design/`, and the markdown update guide into `docs/`.

## Moves (all executed via git mv, tracked as renames)

- `CounselConnect_Initial_Database_v4.sql`, `CounselConnect_Initial_Database_v4.1.sql` → `db/`
- `CounselConnect_DFD_AI_Readable_FULL.md` → `design/DFD_AI_Readable_FULL.md`
- `CounselConnect%20ERD_AI_Readable_FULL.md` → `design/ERD_AI_Readable_FULL.md` (name cleaned)
- `CounselConnect%20Flowchart%20V1_AI_Readable_FULL.md` → `design/Flowchart_V1_AI_Readable_FULL.md` (name cleaned)
- `MARKDOWN_UPDATE_GUIDE.txt` → `docs/MARKDOWN_UPDATE_GUIDE.txt`

## Reference updates (completed)

- `backend/app/tests/conftest.py` — BASELINE_SQL now resolves `db/CounselConnect_Initial_Database_v4.1.sql`.
- `README.md` — layout section lists `db/` and `design/`; both baseline-SQL references updated; setup step points to the guide.
- `.kilo/rules/01-workflow.md` — guide path updated.
- `docs/README.md` — index entry added for `MARKDOWN_UPDATE_GUIDE.txt`.
- `.gitignore` — `.ruff_cache/` ignored.
- Model/env docstrings reference the SQL by name only (no path), verified unchanged and correct.

## Verification (executed)

- `python -m pytest app/tests -q` → **15 passed** against real MySQL (proves the moved baseline SQL still resolves through conftest).
- `git grep` for every old path/filename: only this task log retains old names (as its own record).
- `git status --short`: six renames + five intentional reference edits, nothing else.

## Out of scope (unchanged)

Backend/frontend internal layouts; module files; behavior.

## Human decisions

None needed.
