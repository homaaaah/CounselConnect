# Backend

FastAPI modular monolith for CounselConnect.

## Layout

- app/ — application package
- migrations/ — Alembic migrations
- requirements.txt
- alembic.ini

HTTP routes compose through module routers. Business rules stay in services and persistence stays in repositories.

## Adding backend work

- Add domain code under app/modules/{module_name}.
- Add process infrastructure under app/core.
- Add shared request dependencies/response helpers under app/shared.
- Add database wiring under app/db.
- Add tests under app/tests.
- Use Alembic for every post-baseline schema change.

## Revised target boundaries

Target roles are STUDENT, COUNSELOR, and SUPERADMIN. GUIDANCE_STAFF is legacy and is removed only after automated COR screening is implemented and migrated. Use superadmin naming, not generic admin.

New target modules include cor_screening, calls, counseling_sessions, clinical_documents, and session_observation. Wellness Resource and resource-backed assistant modules are scheduled for removal.

Support multiple Counselors and enforce assigned-Counselor access. Superadmin has no default clinical-content access. Never persist call media or AI observation history. See .ai/DECISIONS.md and .ai/CURRENT_TASK.md before implementation.
