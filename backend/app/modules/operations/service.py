"""operations service: authorization + business rules.

Counselor-only operational workflows (docs/COUNSELOR_DASHBOARD.md):
- account + Guidance Staff management (via accounts service)
- academic profile corrections (via accounts service)
- audit views (via audit service — COUNSELOR-only)

# TODO: Implement after ADR-P01 (authorization context pending).
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.operations.repository import OperationsRepository


class OperationsService:
    """Back-office orchestration rules (delegates to owning modules)."""

    def __init__(self, session: Session) -> None:
        self.repository = OperationsRepository(session)


def get_operations_service(session: Session = Depends(get_session)) -> OperationsService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return OperationsService(session)
