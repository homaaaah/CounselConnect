"""audit service: authorization + business rules.

Core rules (docs/SECURITY.md, docs/COUNSELOR_DASHBOARD.md):
- Modules write minimal operational audit events (past-tense snake_case
  event_type, singular snake_case target_type).
- Reading audit activity is COUNSELOR-only and purpose-bound.
- Metadata must never contain secrets or confidential content (COR refs,
  message bodies, SOS answers).

# TODO: Implement write helpers + authorized read views after ADR-P01.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.audit.models import AuditEvent
from app.modules.audit.repository import AuditRepository


class AuditService(BaseService[AuditEvent]):
    """Audit event business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(AuditRepository(session))


def get_audit_service(session: Session = Depends(get_session)) -> AuditService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return AuditService(session)
