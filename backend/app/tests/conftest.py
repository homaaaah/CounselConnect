"""Shared MySQL fixtures for database-backed tests (session + migration).

The project targets MySQL 8.4 (ADR-002); these fixtures build a dedicated
test schema `counselconnect_test` once per session:

1. drop + create the schema (utf8mb4);
2. apply the canonical v4.1 baseline SQL (the approved schema the dev DB
   also uses; the baseline Alembic revision is intentionally a no-op);
3. stamp the baseline revision, then apply the user_sessions migration by
   calling its own upgrade()/downgrade() functions against the test
   engine — this exercises the real migration code, not just metadata.

Each test runs inside a connection-scoped transaction that is rolled back,
so tests never see each other's rows even when code calls session.commit().

Skipped automatically when MySQL is unreachable or the mysql client
binary cannot be located. Non-DB tests (app/client fixtures below) are
unaffected and keep working as before.
"""

from __future__ import annotations

import importlib.util
import subprocess
from collections.abc import Iterator
from pathlib import Path
from shutil import which

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
BASELINE_SQL = PROJECT_ROOT / "CounselConnect_Initial_Database_v4.1.sql"
MIGRATION_FILE = (
    BACKEND_ROOT / "migrations" / "versions" / "20260904_297c92da239d_add_user_sessions_table.py"
)

TEST_DB_NAME = "counselconnect_test"
BASELINE_REVISION = "8f0f8c585641"


def _find_mysql_client() -> Path | None:
    exe = which("mysql")
    if exe:
        return Path(exe)
    candidate = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")
    return candidate if candidate.exists() else None


def _admin_url() -> str:
    s = get_settings()
    return f"mysql+pymysql://{s.db_user}:{s.db_password}@{s.db_host}:{s.db_port}/?charset=utf8mb4"


def _test_url() -> str:
    s = get_settings()
    return (
        f"mysql+pymysql://{s.db_user}:{s.db_password}"
        f"@{s.db_host}:{s.db_port}/{TEST_DB_NAME}?charset=utf8mb4"
    )


def load_migration_module():
    """Import the user_sessions migration file by path (digit-leading name)."""
    spec = importlib.util.spec_from_file_location("user_sessions_migration", MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def mysql_available() -> bool:
    """True when the configured MySQL server is reachable."""
    try:
        probe = create_engine(_admin_url(), poolclass=NullPool)
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        probe.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def mysql_test_engine(mysql_available):
    """Session-scoped: fresh test schema with baseline + user_sessions applied.

    user_sessions is applied via the migration's own upgrade() so tests
    exercise the actual migration path; downgrade/upgrade cycle tests
    run later in this suite against the same schema.
    """
    if not mysql_available:
        pytest.skip("MySQL not reachable with COUNSELCONNECT_* settings")
    s = get_settings()

    admin = create_engine(_admin_url(), poolclass=NullPool)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(
            text(f"CREATE DATABASE {TEST_DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        )
    admin.dispose()

    mysql_exe = _find_mysql_client()
    if mysql_exe is None:
        pytest.skip("mysql client binary not found; cannot apply baseline SQL")

    # Rewrite the hardcoded database name to the test schema.
    sql = BASELINE_SQL.read_text(encoding="utf-8")
    sql = sql.replace(
        "CREATE DATABASE IF NOT EXISTS counselconnect",
        f"CREATE DATABASE IF NOT EXISTS {TEST_DB_NAME}",
    )
    sql = sql.replace("USE counselconnect;", f"USE {TEST_DB_NAME};")
    proc = subprocess.run(
        [
            str(mysql_exe),
            f"-h{s.db_host}",
            f"-P{s.db_port}",
            f"-u{s.db_user}",
            f"-p{s.db_password}",
            TEST_DB_NAME,
        ],
        input=sql,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"baseline SQL failed: {proc.stderr}"

    engine = create_engine(_test_url(), poolclass=NullPool)

    # Stamp baseline, then run the real migration code to head.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        conn.execute(text(f"INSERT INTO alembic_version VALUES ('{BASELINE_REVISION}')"))

    migration = load_migration_module()
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()

    yield engine

    engine.dispose()
    admin2 = create_engine(_admin_url(), poolclass=NullPool)
    with admin2.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin2.dispose()


@pytest.fixture()
def db_session(mysql_test_engine) -> Iterator[Session]:
    """One connection/transaction per test; rolled back after the test.

    The connection-level transaction keeps each test isolated even when
    code under test calls session.commit() (it joins the outer tx).
    """
    conn = mysql_test_engine.connect()
    outer_tx = conn.begin()
    db = Session(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        yield db
    finally:
        db.close()
        if outer_tx.is_active:
            outer_tx.rollback()
        conn.close()


# ---------------------------------------------------------------------------
# Original app/client fixtures (non-DB tests) — unchanged behavior.
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Fresh application per test (no DB connection required for health)."""
    return create_app()


@pytest.fixture()
def client(app):
    """TestClient bound to the fresh app."""
    return TestClient(app)
