# Registration Corrections: local deployment and rehearsal plan

Target selected by the user on 2026-10-26: **local development, prepare and rehearse**. This plan does not authorize staging/production deployment or migration of the existing application database. Use the [handoff](REGISTRATION_CORRECTIONS_HANDOFF.md) for completed validation and the [owning contract](REGISTRATION_CORRECTIONS.md) for behavior and privacy rules.

Subsequent explicit user authorization on 2026-10-26 permitted stopping the local backend and applying the three release migrations. That local migration is now complete with an encrypted backup/isolated restore and schema/data-preservation verification. The backend remains stopped and functional testing belongs to the user. See the handoff for the actual result and recovery-backup location; this does not authorize other deployments.

## Release contents and prerequisites

Deploy backend and frontend from the same reviewed source snapshot. The current working tree contains substantial modified and untracked release files; a Git commit alone does not represent those additions. Before an actual deployment, choose an immutable release artifact that includes them, excludes `.env`, private stores, credentials and test artifacts, and retains the previous compatible artifact. No commit or packaging of private data is part of this rehearsal.

| Item | Required state |
|---|---|
| Database | MySQL 8.4 LTS; existing schema revision verified before any DDL. |
| Backend | Existing virtual environment/dependencies; current API and schema deployed together. |
| Frontend | Existing locked dependencies and matching `dist` build; `/api` and WebSocket requests forwarded to FastAPI. Vite's development proxy applies only to the local development server. |
| Processes | One backend process for the existing in-memory call registry. Stop every backend process and any other writer during migration; lifespan owns the COR and messaging cleanup threads. |
| Private COR store | Outside served/static folders and version control; readable/writable only by the application identity. Preserve original deadlines. Do not archive COR bytes as release artifacts or create permanent evidence backups. |
| Screening | Existing Poppler/Tesseract and barcode dependencies available through configured paths. Stubbed test extraction does not verify real OCR. |
| Auth/network | Local HTTP uses the existing development cookie setting. HTTPS deployment requires secure cookies, exact allowed origins and correct proxy/cookie/WebSocket transport. Never copy development credentials to a real deployment. |
| Recovery | Before touching an existing DB, verified protected backup and restore procedure, maintenance window, previous artifact, rollback owner and acceptable data-loss window. Backup storage/retention must follow the approved privacy policy; do not invent an indefinite COR archive. |

No new dependency installation, process manager, hosting provider, storage provider or permission model is introduced by this plan.

## Safe local rehearsal

Run from `backend/`. The test URL must explicitly name `counselconnect_test`; the fixtures create and drop only their own randomly named schemas. They never fall back to application tables. Do not print `.env.test` or its URL.

```powershell
# Actual Alembic runner: previous release revision -> pinned release head,
# retry, row preservation, legacy unknowns and pending unique constraint.
.venv/Scripts/python.exe -c "from dotenv import load_dotenv; load_dotenv('.env.test', override=False); import pytest; raise SystemExit(pytest.main(['app/tests/integration/test_registration_release_rehearsal.py','-q','--tb=short','-p','no:cacheprovider']))"

# Optional browser rehearsal: requires Playwright and installed Chrome already
# available locally. Runs synthetic desktop and mobile-sized browser flows
# for both REGISTRATION and CORRECTION proof purposes. No download/install.
.venv/Scripts/python.exe -c "from dotenv import load_dotenv; load_dotenv('.env.test', override=False); import os,pytest; os.environ['COUNSELCONNECT_BROWSER_REHEARSAL']='1'; raise SystemExit(pytest.main(['app/tests/integration/test_management_browser.py','-q','--tb=short','-p','no:cacheprovider']))"

.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe -m alembic heads
```

Browser tests start loopback Vite and FastAPI, use disposable MySQL and temporary private files, stub document extraction, block external font/icon requests, and close their processes. Screenshots contain synthetic data only and are written to pytest's temporary artifact directory. A 390×844 viewport is not a physical mobile device. Native PDF rendering, genuine OCR and camera/TURN require the manual checks below.

Reuse the handoff's relevant 956-test results, 129 frontend tests, two React/API flows and 87-module build when corresponding application source/dependencies are unchanged. New rehearsal checks are additional evidence, not a replacement for that coverage. A source fix requires affected tests and, for frontend application changes, a new production build.

## Existing-database deployment sequence

1. Identify the exact local application database and service commands. Confirm the selected release artifact, backup/restore procedure and maintenance window. Do not assume `.env.test` selects the application DB; Alembic uses application `COUNSELCONNECT_DB_*` settings and `backend/.env`.
2. Put the application into maintenance and stop all writers, including backend processes/cleanup threads. Preserve in-flight decisions and do not run mixed old/new writers against this release. Take the approved database backup while writes are stopped and verify restore in an isolated destination. Do not back up temporary COR bytes indefinitely or restore expired/deleted evidence as usable proof.
3. From `backend/`, inspect the target using `.venv/Scripts/python.exe -m alembic current`. Expected immediate predecessor is `20261024_weekly_sched_softdel`; already-applied release revisions can be resumed after inspection. An older, unversioned, unknown or branched schema needs a separately reviewed path. Never stamp a revision to pretend DDL ran and never load clean-install SQL over existing data.
4. Before DDL, run this aggregate-only query against the confirmed target. Expected result: zero. A nonzero result blocks upgrade; do not auto-return, approve, delete or relabel ambiguous requests. An authorized review must resolve them before retrying.

   ```sql
   SELECT COUNT(*) AS duplicate_pending_owners
   FROM (
       SELECT student_user_id
       FROM profile_change_requests
       WHERE status = 'PENDING'
       GROUP BY student_user_id
       HAVING COUNT(*) > 1
   ) AS duplicate_owners;
   ```

5. Record aggregate row/status counts without names, proposed values, evidence hashes/paths or tokens. With writers still stopped, apply the pinned head:

   ```powershell
   .venv/Scripts/python.exe -m alembic upgrade 20261025_pending_correction
   .venv/Scripts/python.exe -m alembic current
   ```

   The chain is `20261025_correction_context` -> `20261025_account_screening_scope` -> `20261025_pending_correction`. MySQL DDL commits independently; a failed upgrade may leave partial additive DDL. Keep writers stopped, inspect the reported failure and schema, then retry only after resolving the cause. The migrations inspect existing objects for retry; do not patch deployed tables manually.
6. Confirm the exact head, preserved row/status counts, unknown legacy snapshots, false deactivation defaults, registration-purpose defaults and generated unique pending-owner guard. Existing nondefault state must be preserved when resuming an already-used release.
7. Start the matching backend with normal lifespan enabled and one process. For local development only, the existing command is `.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Start Vite from `frontend/` with `npm.cmd run dev -- --host 127.0.0.1`. Use synthetic accounts for smoke checks. Do not run test-only `run_cleanup=False` in the application.
8. Check `/api/v1/health` and an authenticated DB-backed request. Health alone is liveness and does not establish DB readiness. Verify the COR worker reports readiness at the migration head and that bounded expiry/deletion retry resumes without dumping confidential logs. No reset of upload timestamps or restoration of deleted evidence is permitted.
9. Complete the manual matrix, then end maintenance. For any future hosted deployment, serve the matching frontend production artifact with correct API/WebSocket forwarding; the Vite dev server is not the production host.

## Recovery if migration or smoke checks fail

Keep writers stopped or return to maintenance. Prefer fixing forward without rewriting business history. Do not start an older application merely because the schema is additive: old code may ignore deactivation, screening purpose, RETURNED outcomes or retention boundaries.

The pending-owner downgrade only removes the guard/derived column, so it must never run while writers can create competing requests. The scope downgrade refuses nondefault deactivation or correction-purpose rows. The context downgrade refuses populated snapshots/version/evidence context or RETURNED decisions. Never clear those values to force rollback. A full downgrade is possible only when every migration's guards permit it and the selected older artifact remains safe for the actual state.

If recovery requires the pre-upgrade database backup, restore first into an isolated destination and validate it. Coordinate approved data reconciliation before replacing the target; a restore can lose post-backup decisions and session revocations. Do not replay temporary COR bytes, extend original deadlines or revive revoked sessions. Record only safe outcome metadata.

## Remaining manual checks

Use synthetic data and a supported browser. These gates remain distinct from automated evidence.

| Check | Expected result |
|---|---|
| Desktop and mobile navigation | Users/review routes reachable; active Student can reach Registration from app navigation; menu closes after navigation. |
| Users paging and filters | Every page reachable; search/status/role filters use the selected account ID; protected roles have no status action. |
| Status confirmation and sessions | Confirmation identifies the selected synthetic account; disable revokes sessions; re-enable requires a new login and preserves enrollment restrictions. |
| Private PDF | Authorized no-store response; valid synthetic PDF visibly renders; close/navigation/decision revoke preview; mobile browser behavior checked on a device. |
| Concurrent review | Two sessions load the same displayed version; first return/approval wins; second gets safe conflict and refreshes; no second decision or stale profile overwrite. |
| Student revision | Return reason visible; fresh valid synthetic COR and supported change create a new linked version; current fields remain separate until approval. |
| Evidence lifecycle | Decision/replacement/expiry removes retained proof within the original deadline; failed deletion remains retryable; Student enrollment is unaffected by correction expiry. |
| Genuine screening | Approved synthetic COR template exercises installed PDF/barcode/OCR tools without stubbed extraction; no raw OCR/image persistence or authenticity claim. |
| Device/calls | Capacitor and real camera/TURN require physical devices and authorized test participants; no recording or persisted observation history. |

Record actual results and outstanding limits in the handoff/current-task record. Do not mark physical-device or OCR checks passed from a renderer or desktop viewport test.
