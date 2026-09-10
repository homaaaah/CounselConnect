# `.ai/` — Agent Context

| File | Load when |
|---|---|
| `RULES.md` | every non-trivial task |
| `CURRENT_TASK.md` | every non-trivial task |
| `CONTEXT_MAP.md` | choose task-specific context |
| `NAMING_CONVENTIONS.md` | API, database, model, file, or event naming |
| `PROJECT.md` | project-wide scope/facts |
| `ARCHITECTURE.md` | boundaries or cross-module design |
| `REQUIREMENTS.md` | requirement IDs/acceptance constraints |
| `DECISIONS.md` | durable approved and pending choices |
| `CONTRIBUTING.md` | Git/GitHub team workflow (branch-per-task, PR review) |

Default: `RULES` → `CURRENT_TASK` → one `CONTEXT_MAP` route. Detailed feature contracts live in `docs/`; do not bulk-load them.
