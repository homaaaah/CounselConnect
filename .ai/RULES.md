# CounselConnect — AI Development Rules

## Authority

Conflict order: current human/adviser instruction → latest approved decision → owning feature doc → requirements → architecture → implementation/tests. Report unresolved material conflicts; do not invent policy.

## Work discipline

- Load only the context route needed for the task.
- Inspect affected code/tests first; make the smallest coherent change.
- Reuse existing modules; do not silently replace stack, auth, persistence, transport, or business rules.
- Follow `.ai/NAMING_CONVENTIONS.md` for APIs, models, database objects, events, and files.
- Backend authorization is authoritative; hidden UI is not access control.
- Validate all inputs, uploads, CMS data, and external metadata. Externalize secrets and use safe database access.
- Keep confidential data out of logs, errors, URLs, analytics, and unapproved external services.

## Privacy/safety invariants

- Current COR: private temporary storage only; authorized verification access; delete after decision or seven-day TTL; log cleanup outcome, not file content.
- Expression cue: raw camera data stays on-device; no embeddings, cloud inference, persistence, broad logging, diagnosis, or SOS influence.
- Wellness discovery: allowlisted sources, bounded metadata, Counselor review before publication, canonical links, no mirrored full articles/arbitrary hosted thumbnails.
- Messaging: no recordings, generated transcripts, or summaries; purge message bodies 30 days after conversation closure.
- CMS: structured/sanitized content only; never executable/configuration/security/AI-instruction data.
- No psychological diagnosis or medical recommendation.

## Data and tests

- MySQL 8.4 LTS; SQLAlchemy 2.0 + PyMySQL; Alembic. No PostgreSQL-specific assumptions or manual deployed-schema patching.
- Use UTC in storage/API; display `Asia/Manila`.
- Behavior/API/data/security changes require focused automated tests where practical. Always test touched authorization/privacy boundaries.
- Never claim checks passed unless run.

## Documentation

Update only the owning contract plus affected requirement/decision/routing references. Routine progress belongs in `CURRENT_TASK.md` or version-control history, not stable docs.

Completion report: outcome, files changed, checks run, unresolved limitations/decisions.
