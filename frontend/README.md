# Frontend

React (JavaScript, JS/JSX), Vite, TailwindCSS, and Capacitor client for CounselConnect.

## Layout

```text
frontend/
  public/      Static public assets
  src/         Application source
```

Important source folders:

```text
src/
  app/         App composition and route constants
  components/  Shared UI, layout, and feedback components
  features/    Domain-specific frontend code
  hooks/       Global hooks
  pages/       Current route-level pages
  services/    API client and service wrappers
  types/       Shared API DTO notes (plain JavaScript)
  utils/       Shared pure helpers
```

Backend authorization is authoritative. Frontend route hiding is only a user
experience layer, not access control.

