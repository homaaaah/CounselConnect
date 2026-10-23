"""Periodic COR screening expiry/retry worker owned by the FastAPI application."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Event

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.modules.cor_screening.service import CorScreeningService

logger = logging.getLogger(__name__)
CLEANUP_INTERVAL_SECONDS = 60
BACKEND_ROOT = Path(__file__).resolve().parents[3]


def database_readiness() -> tuple[bool, str]:
    """Check DB connectivity and migration head before querying COR tables.

    Migrations remain an explicit deployment/developer operation. The worker
    waits when the database is unavailable or behind, and never runs DDL.
    """
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    except Exception:
        return False, "migration_metadata_unavailable"

    try:
        with get_engine().connect() as connection:
            current_revisions = set(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
            )
    except SQLAlchemyError:
        return False, "database_unavailable_or_unversioned"
    except Exception:
        return False, "database_readiness_check_failed"

    if not expected_heads or current_revisions != expected_heads:
        return False, "schema_not_at_migration_head"
    return True, "ready"


def run_cleanup_once() -> None:
    with Session(get_engine(), expire_on_commit=False) as session:
        CorScreeningService(session).cleanup_due_files()
        session.commit()


def cleanup_loop(stop: Event) -> None:
    """Run when the database is ready and retry without logging sensitive data."""
    last_state: str | None = None
    while not stop.is_set():
        ready, reason = database_readiness()
        if not ready:
            if reason != last_state:
                logger.warning(
                    "cor_screening_cleanup_worker_waiting reason=%s retry_in_seconds=%s",
                    reason,
                    CLEANUP_INTERVAL_SECONDS,
                )
            last_state = reason
        else:
            try:
                run_cleanup_once()
            except SQLAlchemyError:
                reason = "database_operation_failed"
            except OSError:
                reason = "storage_operation_failed"
            except Exception:
                # Do not log exception text: it may contain private config or paths.
                reason = "cleanup_operation_failed"
            else:
                if last_state is not None:
                    logger.info("cor_screening_cleanup_worker_ready")
                reason = "ready"

            if reason != "ready" and reason != last_state:
                logger.error(
                    "cor_screening_cleanup_worker_failed reason=%s retry_in_seconds=%s",
                    reason,
                    CLEANUP_INTERVAL_SECONDS,
                )
            last_state = reason
        if stop.wait(CLEANUP_INTERVAL_SECONDS):
            break


if __name__ == "__main__":
    run_cleanup_once()
