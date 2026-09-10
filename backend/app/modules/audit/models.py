"""audit ORM model: audit_events.

Mirrors CounselConnect_Initial_Database_v4.sql exactly. Polymorphic target;
minimal operational metadata; authorized COUNSELOR read access only.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_events_actor", "actor_user_id", "occurred_at"),
        Index("idx_audit_events_target", "target_type", "target_id", "occurred_at"),
        Index("idx_audit_events_type", "event_type", "occurred_at"),
    )

    audit_event_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_audit_events_actor", ondelete="SET NULL", onupdate="CASCADE"),
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    occurred_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
