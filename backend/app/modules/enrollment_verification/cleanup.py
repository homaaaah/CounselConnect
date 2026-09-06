"""Periodic COR expiry/retry worker owned by the FastAPI application."""

from __future__ import annotations

import logging
from threading import Event

from sqlalchemy.orm import Session

from app.database import get_engine
from app.modules.enrollment_verification.service import EnrollmentVerificationService

logger = logging.getLogger(__name__)
CLEANUP_INTERVAL_SECONDS = 60


def run_cleanup_once() -> None:
    with Session(get_engine(), expire_on_commit=False) as session:
        EnrollmentVerificationService(session).cleanup_due_files()
        session.commit()


def cleanup_loop(stop: Event) -> None:
    """Run on startup and every minute; log failures without sensitive data."""
    while not stop.is_set():
        try:
            run_cleanup_once()
        except Exception:
            # Avoid exception text: DB URLs and storage paths may be private.
            logger.error("verification_cleanup_worker_failed; retry scheduled")
        if stop.wait(CLEANUP_INTERVAL_SECONDS):
            break


if __name__ == "__main__":
    run_cleanup_once()
