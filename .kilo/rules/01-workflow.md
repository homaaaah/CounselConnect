# CounselConnect — Kilo Workflow

Root `AGENTS.md` is authoritative. Keep this rule focused on task execution; do not duplicate project facts.

## Start every implementation task

1. Populate `.ai/CURRENT_TASK.md` before changing code. Replace stale content and set:
   - `Status: ACTIVE`
   - one observable objective
   - one route from `.ai/CONTEXT_MAP.md`
   - explicit in/out scope
   - testable acceptance criteria
   - planned verification
   - unresolved human decisions
2. Read only that context route and affected code/tests. Batch independent reads.
3. For API/schema/model/migration work, also read `.ai/NAMING_CONVENTIONS.md`.
4. If documentation or a durable contract may change, read `docs/MARKDOWN_UPDATE_GUIDE.txt` before editing docs. Otherwise do not load it.
5. If a material decision is missing, set the task `BLOCKED`, record the decision needed, and ask the user instead of inventing policy.

Read-only questions and trivial explanations do not require updating `CURRENT_TASK.md`.

## Risk classification

- **LOW:** copy, comments, documentation wording, styling, or isolated presentation behavior with no data/security/business effect.
- **MEDIUM:** localized application behavior, API/UI integration, state handling, or persistence logic that does not change a sensitive boundary.
- **HIGH:** authentication/authorization, roles, MySQL schema/migrations, COR handling, message retention, SOS, expression-cue privacy, external-resource fetching, CMS sanitization, secrets, or cross-module workflows.

When uncertain, use the higher class.

## Act and verify

- Inspect before editing; implement the smallest coherent change.
- Run the narrowest relevant build/lint/test commands. Add focused tests for behavior, API, data, or security changes.
- Never claim a check passed unless it ran.
- After two failed attempts without new evidence, stop the loop, update `CURRENT_TASK.md`, and report the blocker.
- Update durable docs only when their contract changed.

## Risk-based review

- **All tasks:** inspect the final diff for scope creep, accidental edits, naming violations, and unsupported claims.
- **LOW:** focused self-check is sufficient; no separate reviewer task.
- **MEDIUM:** perform one read-only in-task review against acceptance criteria, the relevant feature contract, and test results. Fix confirmed issues, then rerun affected checks.
- **HIGH:** require a fresh read-only review before acceptance. Run Kilo's `/review` workflow in a new session when available; otherwise use the Ask agent with an explicit review-only prompt. Review authorization/privacy, state transitions, migration/retention effects, error paths, regressions, and tests. Use the Code agent only for confirmed fixes, then rerun affected checks.

## Finish

Update `.ai/CURRENT_TASK.md` with `Status: COMPLETED` or `BLOCKED`, actual verification results, remaining limitations, and human decisions still needed. Report outcome, files changed, exact checks, and unresolved risks.

Use Graphify guidance in root `AGENTS.md` when its graph exists.
