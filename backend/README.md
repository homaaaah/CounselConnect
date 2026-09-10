# Backend

FastAPI modular monolith for CounselConnect.

## Layout

```text
backend/
  app/          Application package
  migrations/   Alembic migrations
  requirements.txt
  alembic.ini
```

Inside `app/`, HTTP routes compose through module routers. Business behavior
should stay in module services, and persistence should stay in repositories.

## Adding Backend Work

- Add domain code under `app/modules/{module_name}`.
- Add shared process infrastructure under `app/core`.
- Add shared request dependencies and response helpers under `app/shared`.
- Add database base/session/mixins under `app/db`.
- Add backend tests under the existing `app/tests` tree until a dedicated test
  migration is approved.

Do not add an Administrator role. Use only `STUDENT`, `GUIDANCE_STAFF`, and
`COUNSELOR`.

