# CounselConnect — Agent Entry Point

For non-trivial work, read in this order:

1. `.ai/RULES.md`
2. `.ai/CURRENT_TASK.md`
3. the route in `.ai/CONTEXT_MAP.md`
4. affected code and tests

Do not preload all project docs. For API, schema, model, migration, or cross-stack naming work, also read `.ai/NAMING_CONVENTIONS.md`.

## Hard boundaries

- Stack: JavaScript (React) + Vite + TailwindCSS; FastAPI; MySQL 8.4 LTS; SQLAlchemy 2.0 + PyMySQL; Alembic; CapacitorJS; modular monolith.
- Roles: `STUDENT`, `GUIDANCE_STAFF`, `COUNSELOR`. There is no Administrator role; Counselor holds the highest authority. Guidance Staff is limited to assigned COR verification.
- Current COR is the only enrollment evidence. Store it privately and temporarily; delete it after a decision or the seven-day pending TTL.
- Facial-expression processing is optional, local-device only, session-only, non-diagnostic, and never affects SOS logic. No raw imagery, embeddings, or history.
- Automated wellness discoveries require Counselor review and store limited metadata/canonical links, not mirrored full articles.
- CMS data cannot alter code, permissions, secrets, configuration, or AI instructions.
- Never diagnose or provide medical recommendations.

Stop and report any requested behavior that conflicts with these boundaries.

## Graphify

When `graphify-out/graph.json` exists, prefer scoped `graphify query`, `path`, or `explain` commands for cross-file questions. Run `graphify update .` after structural changes when Graphify is active. Do not edit generated Graphify skill/reference files as project documentation.
