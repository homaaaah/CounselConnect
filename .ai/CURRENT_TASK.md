# CounselConnect — Current Task

**Status:** COMPLETED
**Risk class:** HIGH (authentication/session storage; MySQL schema migration)

## Objective

Create the MySQL-backed `user_sessions` table, its SQLAlchemy 2.0 model, an Alembic upgrade/downgrade migration, and the repository operations needed for revocable opaque login sessions — without implementing login/cookie/CSRF routes (still pending ADR-P01).

## Context route

`auth-rbac` (`.ai/RULES.md`, this file, `docs/USER_ROLES.md`, `docs/SECURITY.md`), plus `api-or-schema` inputs (`docs/DATABASE.md`, `.ai/NAMING_CONVENTIONS.md`, `docs/API_CONTRACT.md`). ADRs reviewed: ADR-002, ADR-003, ADR-005, ADR-015. **ADR-019/020/021 (requested in the task brief) do not exist** — `.ai/DECISIONS.md` ends at ADR-018; session policies (1h idle / 12h absolute / heartbeat rule) come from the task instruction (top authority per `.ai/RULES.md`) and are recorded in `docs/SECURITY.md`.

## Delivered

- `backend/app/modules/auth/models.py` — `UserSession` ORM model (BINARY(32) digests, timeline + revocation-shape CHECKs, unique token_hash, user/active + cleanup indexes, FK CASCADE).
- `backend/migrations/versions/20260904_297c92da239d_add_user_sessions_table.py` — revision `297c92da239d`, revises `8f0f8c585641`. Upgrade creates only `user_sessions`; downgrade drops FK then table only (MySQL 1553-safe).
- `backend/app/modules/auth/repository.py` — create (hash-only inputs), lookup by token hash, list per user, explicit `touch_session` clamped to `absolute_expires_at`, revoke one, revoke all for user, delete expired/revoked cleanup.
- `backend/app/db/base.py` — fixed pre-existing `ck` naming-convention bug (`chk_%(table_name)s_%(constraint_name)s` double-prefixed every CHECK; now `%(constraint_name)s` passthrough matching deployed v4.1 names). Autogenerate previously would have renamed every CHECK constraint in the DB; verified clean autogenerate (empty drift revision) after the fix.
- `backend/app/db/base.py` — `import_all_models()` now registers `app.modules.auth.models`.
- `backend/app/tests/conftest.py` — MySQL test-schema fixtures: session-scoped `counselconnect_test` built from the canonical v4.1 SQL + real migration code; per-test savepoint-rollback `db_session`; original app/client fixtures preserved.
- `backend/app/tests/unit/test_user_sessions.py` — 10 focused tests covering all required behaviors.
- `docs/DATABASE.md` — `user_sessions` group entry; Alembic-ownership + session integrity notes.
- `docs/SECURITY.md` — "Login sessions" policy section (1h idle / 12h absolute / heartbeat rule / revocation semantics) + sensitive-data matrix row.

## Final table contract (as verified in MySQL)

Columns: `session_id` BIGINT UNSIGNED PK AUTO_INCREMENT; `user_id` BIGINT UNSIGNED NOT NULL FK→users(user_id) ON DELETE/UPDATE CASCADE; `token_hash` BINARY(32) NOT NULL UNIQUE; `csrf_token_hash` BINARY(32) NOT NULL; `created_at`/`last_activity_at`/`absolute_expires_at` DATETIME(6) NOT NULL (UTC); `revoked_at` DATETIME(6) NULL; `revocation_reason` VARCHAR(50) NULL.

Constraints: `uq_user_sessions_token_hash`; `chk_user_sessions_timeline` (`last_activity_at >= created_at AND absolute_expires_at >= last_activity_at`); `chk_user_sessions_revocation_shape` (revoked_at <-> revocation_reason both-null-or-both-set); `fk_user_sessions_user` CASCADE/CASCADE.

Indexes: `idx_user_sessions_user_active` (user_id, revoked_at, absolute_expires_at); `idx_user_sessions_cleanup` (absolute_expires_at, revoked_at).

FK behavior rationale: sessions are ephemeral credentials, not user history — CASCADE keeps user deletion unblocked; `audit_events` keeps its SET NULL because it is the durable record.

## Verification (executed 2026-09-04, MySQL 8.4.11 dev DB)

1. `python -m alembic upgrade head` (dev DB) → `SHOW CREATE TABLE user_sessions` verified all columns/types/constraints/indexes; `alembic_version` = `297c92da239d`.
2. `python -m alembic downgrade -1` (dev DB) → `user_sessions` gone, version back to `8f0f8c585641`, all other tables intact; `upgrade head` restored it.
3. `python -m alembic revision --autogenerate` produced an empty (zero-drift) revision → model, migration, and live DB agree exactly; throwaway revision deleted.
4. `python -m pytest app/tests -q` → **15 passed** (5 existing + 10 new `test_user_sessions.py`), against real MySQL `counselconnect_test` schema (v4.1 baseline SQL + migration code path).
5. Test DB dropped automatically after the session.

New-test coverage: upgrade shape on live MySQL; downgrade removes only its own objects; duplicate token_hash rejected; nonexistent-user FK rejected; hash-only create/lookup; activity updates without extending absolute expiry (clamp); idle/absolute/revoked classified inactive; revoke-one + revoke-all idempotency; cleanup deletes eligible sessions and never users; UTC DATETIME(6) round-trip with microsecond precision.

## Remaining limitations / human decisions

- ADR-P01 (auth mechanism/transport/recovery) still PENDING: login/refresh/logout routes remain honest 501 placeholders; `get_current_user` still `NotImplementedError`; no `.env` auth vars added. The session *service* layer (credential generation via `secrets`, constant-time comparison, cookie transport, CSRF verification) is intentionally NOT implemented.
- Revocation-reason value set (e.g. `USER_LOGOUT`, `ACCOUNT_DISABLED` placeholders used in tests) will be formalized by ADR-P01.
- Repo not committed/pushed (user has not requested commits for this task).

## Files changed

- Added: `backend/app/modules/auth/models.py`, `backend/migrations/versions/20260904_297c92da239d_add_user_sessions_table.py`, `backend/app/tests/unit/test_user_sessions.py`
- Modified: `backend/app/modules/auth/repository.py`, `backend/app/db/base.py`, `backend/app/tests/conftest.py`, `docs/DATABASE.md`, `docs/SECURITY.md`, `.ai/CURRENT_TASK.md`
