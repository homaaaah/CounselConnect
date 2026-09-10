"""audit repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.audit.models import AuditEvent


class AuditRepository(BaseRepository[AuditEvent]):
    """Owns all audit-event SQLAlchemy queries."""

    model = AuditEvent

    def list_filtered(
        self,
        event_type: str | None = None,
        target_type: str | None = None,
        actor_user_id: int | None = None,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Filtered operational/audit activity for authorized views."""
        stmt = select(AuditEvent)
        if event_type is not None:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if target_type is not None:
            stmt = stmt.where(AuditEvent.target_type == target_type)
        if actor_user_id is not None:
            stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
        return list(self.session.scalars(stmt.order_by(AuditEvent.occurred_at.desc()).limit(limit)))
