# Backend Application Package

`backend/app` contains the FastAPI application package.

```text
app/
  core/       Configuration, security, logging, notifications, exceptions
  db/         SQLAlchemy base, mixins, and session helpers
  modules/    Domain modules
  shared/     Shared dependencies, enums, pagination, response helpers
  tests/      Current backend tests
```

Keep cross-module behavior behind service methods. Avoid direct repository or
model access from another module unless there is no service boundary yet and
the coupling is documented in the owning task.

