"""Exercise the actual Alembic runner on an owned pre-release schema."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.config import get_settings
from .test_correction_context_migration import old_schema  # noqa: F401
from ..conftest import load_account_screening_scope_migration_module


def test_alembic_release_upgrade_preserves_existing_rows(old_schema, monkeypatch):
    # old_schema owns this randomly named database and drops it on teardown.
    assert old_schema.url.database.startswith("counselconnect_test_")
    with old_schema.connect() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            load_account_screening_scope_migration_module().downgrade()
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('20261024_weekly_sched_softdel')"))
        before = list(connection.execute(text(
            "SELECT change_request_id, student_user_id, status, requested_first_name, reviewed_at "
            "FROM profile_change_requests ORDER BY change_request_id")))
        connection.commit()
    url = old_schema.url
    for key, value in {"DB_HOST": url.host, "DB_PORT": url.port or 3306,
                       "DB_NAME": url.database, "DB_USER": url.username,
                       "DB_PASSWORD": url.password}.items():
        monkeypatch.setenv(f"COUNSELCONNECT_{key}", str(value or ""))
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    try:
        command.upgrade(config, "20261025_pending_correction")
        command.upgrade(config, "20261025_pending_correction")  # no-op retry
        with old_schema.connect() as connection:
            assert MigrationContext.configure(connection).get_current_heads() == ("20261025_pending_correction",)
            assert list(connection.execute(text(
                "SELECT change_request_id, student_user_id, status, requested_first_name, reviewed_at "
                "FROM profile_change_requests ORDER BY change_request_id"))) == before
            assert connection.scalar(text("SELECT COUNT(*) FROM users WHERE is_deactivated <> 0")) == 0
            assert connection.scalar(text("SELECT COUNT(*) FROM cor_screenings WHERE purpose <> 'REGISTRATION'")) == 0
            assert connection.scalar(text(
                "SELECT COUNT(*) FROM profile_change_requests WHERE submission_version IS NOT NULL "
                "OR registered_values_json IS NOT NULL OR evidence_file_id IS NOT NULL")) == 0
            inspector = inspect(connection)
            assert any(item["name"] == "uq_profile_change_requests_pending_student"
                       for item in inspector.get_unique_constraints("profile_change_requests"))
    finally:
        get_settings.cache_clear()
