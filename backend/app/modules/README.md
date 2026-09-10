# Backend Modules

Each folder in this directory is a business module.

Preferred module file roles:

- `router.py`: HTTP routes and transport-specific parsing
- `schemas.py`: Pydantic request and response schemas
- `service.py`: authorization, privacy checks, and business transitions
- `repository.py`: database reads and writes
- `models.py`: SQLAlchemy models
- `exceptions.py`: module-specific exception types, when needed

Routes should stay thin. Services own business rules. Repositories should not
decide permissions.

