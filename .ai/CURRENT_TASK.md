# CounselConnect — Current Task

**Status:** ACTIVE
**Risk class:** MEDIUM (dev-serving configuration change; no backend code, schema, auth boundary, or API behavior change)

**Task:** Make the dev-tunnel URL (https://m9htjn94-5173.asse.devtunnels.ms) serve a working app: same-origin API access through the Vite dev proxy so session cookie + CSRF flow works over the public tunnel, replacing the cross-origin `http://localhost:8000` base that browsers block (mixed content) and CORS/cookies reject.

**Route (CONTEXT_MAP):** `project` → `.ai/PROJECT.md`; affected: `frontend/vite.config.js`, `frontend/.env` (untracked, local), `frontend/.env.example`, `backend/.env` CORS entry (untracked, local).

**Objective (observable):** Loading the tunnel URL shows the landing page, `GET /api/v1/auth/csrf` (401 without a session / 200 with one) responds through the tunnel same-origin, sign-in works, the session cookie round-trips, and the API status corner reads `API status: ok`.

## In scope

- `frontend/vite.config.js`: add `server.proxy` for `/api` → `http://127.0.0.1:8000` (changeOrigin, xdg-forwarded headers).
- `frontend/.env` + `.env.example`: `VITE_API_BASE_URL=/api/v1` (relative base, same-origin via the proxy).
- `backend/.env`: add the tunnel origin to `COUNSELCONNECT_CORS_ORIGINS` (harmless for the proxy path; needed if a stray absolute call ever happens).
- Verify through the tunnel URL; run `npm test` to confirm no frontend regression (base URL only changes transport, tests mock fetch).

## Out of scope

- Backend code/config changes (cookie_secure stays False for localhost; tunnel is HTTPS-terminated at the proxy, and the proxy passes cookies fine).
- Production build/deploy (Capacitor/prod hosts use their own env; unchanged).

## Acceptance criteria

1. Tunnel URL loads and session restore reaches the backend (401 without session, not "API unreachable").
2. Sign-in through the tunnel sets the session cookie and the app renders authenticated pages.
3. `npm test` 30/30 still passes (or env-independent).
4. Local `http://localhost:5173` still works unchanged.

## Planned verification

- PowerShell `Invoke-WebRequest` probes through the tunnel: `/` 200, `/api/v1/health` 200 `{"status":"ok"}`, `/api/v1/auth/csrf` 401 (no cookie) — all through `https://m9htjn94-5173.asse.devtunnels.ms`.
- `npm test` in frontend (register harness injects its own env; unaffected).
- `npm run build` still succeeds (relative base is valid for vite).

## Unresolved human decisions

- None.

## Verification log

- (pending)
