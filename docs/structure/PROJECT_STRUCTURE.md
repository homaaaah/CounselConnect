# CounselConnect Project Structure

This document describes the current repository layout and the intended home for
new files. It is intentionally additive: existing files stay where they are
unless a separate migration task explicitly moves them.

## Repository Root

```text
COUNSELCONNECT/
  .ai/          Codex and project-governance context
  backend/      FastAPI modular monolith, Alembic, backend tests
  contracts/    Generated or committed API contracts
  db/           Reference SQL snapshots and database exports
  design/       Large source diagrams and readable diagram exports
  docs/         Product, workflow, security, and technical documentation
  frontend/     JavaScript (React)/Vite/Tailwind client and Capacitor shell
```

Root files should stay limited to repository-wide setup, ignore rules, and
entry documentation. Avoid adding feature code at the root.

## Backend

```text
backend/
  app/
    core/       Process-wide infrastructure: config, security, logging, errors
    db/         SQLAlchemy base, mixins, and session wiring
    modules/    Business modules
    shared/     Shared dependencies, response helpers, enums, pagination
    tests/      Current backend tests
  migrations/   Alembic environment and version scripts
```

Backend request flow follows:

```text
router -> schema -> service -> repository -> model
```

Business rules belong in services. Repositories should stay persistence-focused.
React code must not duplicate backend authorization or privacy rules.

## Backend Modules

Current module homes:

```text
accounts/
appointments/
assistant/
audit/
auth/
content/
enrollment_verification/
messaging/
operations/
sos/
wellness_resources/
```

When adding module files, prefer these names:

- `router.py` for HTTP routes
- `schemas.py` for request/response DTOs
- `service.py` for business rules
- `repository.py` for data access
- `models.py` for SQLAlchemy models
- `exceptions.py` only when module-specific errors are needed

Do not add an `admin` module. CounselConnect roles are `STUDENT`,
`GUIDANCE_STAFF`, and `COUNSELOR`.

## Frontend

```text
frontend/
  src/
    app/        App composition and route constants
    components/ Shared layout, UI, and feedback components
    features/   Domain-focused frontend logic
    hooks/      Global hooks
    pages/      Current route-level pages
    services/   API client and service adapters
    types/      Shared API type/shaped modules
    utils/      Shared pure helpers
```

New domain behavior should start under `src/features/{feature_name}`. Shared UI
belongs in `src/components`; API transport belongs in `src/services`.

## Frontend Features

Use this shape when a feature grows beyond one or two files:

```text
features/{feature_name}/
  api/          Feature-specific API wrappers
  components/   Feature-only UI components
  hooks/        Feature-only hooks
  pages/        Feature route pages, when they are not shared route shells
  index.js     Public exports for the feature
```

Keep API DTO fields in `snake_case` to match the backend contract. Convert to
UI-friendly naming only inside local presentation logic when needed.

## Documentation

Current docs are mostly flat. New documentation should use this grouping when
it does not conflict with an existing owning document:

```text
docs/
  structure/     Repository organization notes
  architecture/  System and stack design notes
  api/           API usage and contract notes
  database/      Schema, migration, and ERD notes
  diagrams/      Diagram-specific explanations
  workflows/     Cross-feature user and system flows
  security/      Auth, privacy, and operational safety notes
```

Existing docs remain authoritative according to `.ai/CONTEXT_MAP.md` and
`.ai/RULES.md`. Do not duplicate stable product rules in a new folder unless
the owning document is updated or linked clearly.

## Storage

Private COR files must remain outside committed source control and under the
configured private backend storage path. Never commit uploaded COR files,
secrets, local database dumps with private data, or generated runtime caches.

