# CounselConnect — Current Task

**Status:** COMPLETED (2026-09-10)
**Risk class:** HIGH (stack migration of the whole frontend from TypeScript to JavaScript; broad blast radius, no backend/API/schema/auth change)

**Task:** Migrate the frontend from TypeScript (`.ts`/`.tsx`) to JavaScript (`.js`/`.jsx`), aligning the code with the documented stack (ADR-001: JavaScript (React) + Vite + TailwindCSS; root `AGENTS.md`).

**Route (CONTEXT_MAP):** `project` → `.ai/PROJECT.md`; affected: all 41 modules under `frontend/src/**`, `frontend/{vite.config, capacitor.config, tsconfig.json, package.json, index.html}`, `frontend/tests/register-typescript.cjs` + 5 test files, `frontend/README.md`.

## Objective (observable)

`git ls-files 'frontend/**/*.ts' 'frontend/**/*.tsx'` returns nothing; `npm test` 29/29; `npm run build` clean; `npm run dev` serves the app; no TypeScript tooling remains in dependencies or scripts.

## Outcome

- **Basis:** branched `frontend/migrate-to-javascript-v2` from `fix/appointment-past-slots` (includes appointments past-slot fix) + merged `origin/frontend/app-navbar` (navbar/landing-header work) — the migration covers ALL current work, superseding the stale old `frontend/migrate-to-javascript` branch (based pre-landing-port; left untouched on GitHub).
- **Source (40 renames):** every `.ts`→`.js` / `.tsx`→`.jsx`, stripped interfaces/type annotations/generics/`as const`/type-only imports; all value exports preserved (incl. `EMPTY_FORM`, `ApiError`, `setCsrfToken`, `manilaToday`, `slotIsPast`, `AppNavBar` default); comments updated where they referenced TS files (`types/api` note, `ui/index` test-colocation note).
- **Configs:** `vite.config.js`, `capacitor.config.js` (typed imports dropped, values identical); `index.html` entry `/src/main.jsx`; deleted `tsconfig.json`, `src/vite-env.d.ts`, `tsconfig.tsbuildinfo` (untracked).
- **Tooling:** `package.json` build = `vite build` (tsc removed); removed `typescript`, `@types/react`, `@types/react-dom`; added `esbuild ~0.21.5` (matches Vite's bundled version) for the Node test harness; lockfile regenerated.
- **Tests:** `register-typescript.cjs` (tsc transpile) → `register-app.cjs` (esbuild `transformSync`, jsx automatic, `import.meta.env` shim); all 5 test/live files' requires updated to `.js`/`.jsx` paths. No assertion changes.
- **Docs:** `frontend/README.md` language line + `types/` description updated. `.ai/DECISIONS.md` ADR-001 already stated JavaScript — code now matches the documented stack; no doc contract changed.

## Verification (run 2026-09-10)

- `npm test` — 29/29 PASS (session 10, appointments 11, navbar 9 = includes month-grid, past-slot, navigation tests) on the migrated JS/JSX modules.
- `npm run build` — PASS: 53 modules, 209.17 kB (TS build was 209.39 kB; same CSS hash, near-identical bundle).
- `npm run dev` smoke — PASS: server on 5173, `/` 200, `main.jsx` transforms 200.
- Read-only HIGH-risk review performed: value exports compared file-by-file (all survive); hook dependency arrays identical; aria attributes identical across all 8 TSX→JSX components; string literals verified present (diff artifacts were line-wrap/import-type only); `node --check` on all 27 `.js` files (JSX files verified via esbuild/vite instead); no `.ts`/`.tsx` tracked or on disk under `frontend/`; restored non-TS casualties of an initial over-broad `git rm` (`index.css`, `.gitkeep`s, `features/README.md`).
- Old branch `origin/frontend/migrate-to-javascript` untouched for reference.

## Remaining limitations

- No static type checking anymore (TS strict mode retired). CI safety net is the 29-test suite + build; consider adding ESLint later if wanted.
- Live-HTTP integration tests (`live-flow.cjs`, `live-appointments.cjs`) require a running backend loopback server; not executed here (syntax-checked only).
- `node --test` still discovers only `tests/*.test.cjs`; the two live scripts stay invoked by backend pytest.

## Human decisions

- (none outstanding)
