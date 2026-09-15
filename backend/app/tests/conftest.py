"""Isolated tests: no fallback to the application's database or file store.

DB tests require COUNSELCONNECT_TEST_DATABASE_URL with database name
counselconnect_test. Each run creates a unique schema on that explicit
server, applies the real baseline/migration, and drops only its own schema.
Ordinary app/client fixtures cannot connect to any database.
"""

from __future__ import annotations

import importlib.util
import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import get_session
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
BASELINE_SQL = PROJECT_ROOT / "db" / "CounselConnect_Initial_Database_v4.1.sql"
MIGRATION_FILE = (
    BACKEND_ROOT
    / "migrations"
    / "versions"
    / "20260904_297c92da239d_add_user_sessions_table.py"
)
BLOCKED_DATES_MIGRATION_FILE = (
    BACKEND_ROOT / "migrations" / "versions" / "20260909_blocked_dates.py"
)
RECURRING_SCHEDULES_MIGRATION_FILE = (
    BACKEND_ROOT / "migrations" / "versions" / "20260910_recurring_schedules_and_blocks.py"
)

TEST_DB_NAME = "counselconnect_test"
BASELINE_REVISION = "8f0f8c585641"


def _test_url():
    raw = os.environ.get("COUNSELCONNECT_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set COUNSELCONNECT_TEST_DATABASE_URL for MySQL tests")
    try:
        url = make_url(raw)
    except Exception:
        pytest.fail("Invalid test database URL (value withheld)", pytrace=False)
    if url.drivername != "mysql+pymysql" or url.database != TEST_DB_NAME:
        pytest.fail(
            "Test URL must use mysql+pymysql and database counselconnect_test",
            pytrace=False,
        )
    return url


def load_migration_module():
    """Import the user_sessions migration file by path (digit-leading name)."""
    spec = importlib.util.spec_from_file_location(
        "user_sessions_migration", MIGRATION_FILE
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_blocked_dates_migration_module():
    spec = importlib.util.spec_from_file_location("blocked_dates_migration", BLOCKED_DATES_MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_recurring_schedules_migration_module():
    spec = importlib.util.spec_from_file_location(
        "recurring_schedules_migration", RECURRING_SCHEDULES_MIGRATION_FILE
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def mysql_test_engine():
    """Create, own, and remove a randomly named disposable MySQL schema."""
    from pymysql.constants import CLIENT
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    url = _test_url()
    schema = f"{TEST_DB_NAME}_{uuid.uuid4().hex}"
    assert re.fullmatch(r"counselconnect_test_[0-9a-f]{32}", schema)
    admin = create_engine(
        url.set(database="mysql"),
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )
    engine = None
    created = False
    try:
        with admin.connect() as conn:
            # Deliberately no IF NOT EXISTS: never take ownership of an
            # existing schema, and never drop anything before creation.
            conn.execute(
                text(
                    f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            )
            created = True
        engine = create_engine(
            url.set(database=schema),
            poolclass=NullPool,
            connect_args={
                "client_flag": CLIENT.MULTI_STATEMENTS,
                "init_command": "SET time_zone = '+00:00'",
            },
        )
        sql = BASELINE_SQL.read_text(encoding="utf-8")
        assert sql.count("CREATE DATABASE IF NOT EXISTS counselconnect") == 1
        assert sql.count("USE counselconnect;") == 1
        sql = sql.replace(
            "CREATE DATABASE IF NOT EXISTS counselconnect",
            f"CREATE DATABASE IF NOT EXISTS `{schema}`",
        )
        sql = sql.replace("USE counselconnect;", f"USE `{schema}`;")
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute(sql)
                while cursor.nextset():
                    pass
            raw.commit()
        finally:
            raw.close()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            conn.execute(
                text("INSERT INTO alembic_version VALUES (:revision)"),
                {"revision": BASELINE_REVISION},
            )
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                load_migration_module().upgrade()
                load_blocked_dates_migration_module().upgrade()
                load_recurring_schedules_migration_module().upgrade()
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as conn:
                conn.execute(text(f"DROP DATABASE `{schema}`"))
        admin.dispose()


@pytest.fixture()
def db_session(mysql_test_engine) -> Iterator[Session]:
    """One connection/transaction per test; rolled back after the test.

    The connection-level transaction keeps each test isolated even when
    code under test calls session.commit() (it joins the outer tx).
    """
    conn = mysql_test_engine.connect()
    outer_tx = conn.begin()
    db = Session(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield db
    finally:
        db.close()
        if outer_tx.is_active:
            outer_tx.rollback()
        conn.close()


# ---------------------------------------------------------------------------
# No test may reach the ordinary app database, COR store, or SMTP server.
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_settings(monkeypatch, tmp_path):
    values = {
        "COOKIE_SECURE": "false",
        "COR_MAX_MB": "10",
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "1",
        "DB_NAME": "test_connection_forbidden",
        "DB_USER": "test",
        "DB_PASSWORD": "",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
        "COR_STORAGE_ROOT": str(tmp_path / "cor"),
        "RESOURCE_STORAGE_ROOT": str(tmp_path / "resources"),
    }
    for key, value in values.items():
        monkeypatch.setenv(f"COUNSELCONNECT_{key}", value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def forbid_application_database(monkeypatch, isolated_settings):
    def forbidden():
        raise AssertionError(
            "Use db_session/db_client; the application database is forbidden in tests"
        )

    monkeypatch.setattr("app.database.get_engine", forbidden)


@pytest.fixture()
def app():
    app = create_app(run_cleanup=False)

    def unbound_session():
        with Session() as session:
            yield session

    app.dependency_overrides[get_session] = unbound_session
    return app


@pytest.fixture()
def client(app):
    """TestClient bound to the fresh app."""
    return TestClient(app)


@pytest.fixture()
def db_client(app, db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


@pytest.fixture()
def academic_references(db_session):
    from app.modules.accounts.models import Campus, Department, Program

    campus = Campus(campus_name="Test Campus")
    department = Department(department_name="Test Department")
    db_session.add_all([campus, department])
    db_session.flush()
    program = Program(
        department_id=department.department_id,
        program_code="TEST",
        program_name="Test Program",
    )
    db_session.add(program)
    db_session.flush()
    return campus.campus_id, program.program_id
