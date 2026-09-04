"""content ORM models: content_items, emergency_contacts.

Mirrors CounselConnect_Initial_Database_v4.sql exactly. CMS data can never
alter code, permissions, secrets, configuration, or AI instructions.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("content_key", name="uq_content_items_key"),
        Index("idx_content_items_type_published", "content_type", "is_published"),
        Index("idx_content_items_created_by", "created_by_user_id"),
        Index("idx_content_items_updated_by", "updated_by_user_id"),
        CheckConstraint(
            "content_type IN ('CMS_BLOCK', 'FAQ', 'ANNOUNCEMENT')",
            name="chk_content_items_type",
        ),
    )

    content_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_key: Mapped[str | None] = mapped_column(String(150))
    title: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    is_published: Mapped[bool] = mapped_column(nullable=False, server_default=text("FALSE"), insert_default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_content_items_creator", ondelete="SET NULL", onupdate="CASCADE"),
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_content_items_updater", ondelete="SET NULL", onupdate="CASCADE"),
    )
    created_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    updated_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow, onupdate=utcnow)


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    __table_args__ = (Index("idx_emergency_contacts_active", "is_active", "display_order"),)

    contact_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("TRUE"), insert_default=True)
    display_order: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
