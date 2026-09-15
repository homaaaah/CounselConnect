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

API requests and COR downloads default to `/api/v1` on the page's origin.
During development, Vite proxies `/api` to `http://127.0.0.1:8000`; start
the backend separately. Production hosting must forward `/api` to FastAPI.
To use a separate API host, set `VITE_API_BASE_URL` before starting or building
Vite and configure backend CORS and cookie transport for that deployment.

