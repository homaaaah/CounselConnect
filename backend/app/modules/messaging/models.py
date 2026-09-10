"""messaging ORM models: conversations, messages.

Mirrors CounselConnect_Initial_Database_v4.sql exactly (conversation types,
lifecycle CHECK, 30-day purge marker, idempotent client_message_id).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_student", "student_user_id", "status", "started_at"),
        Index("idx_conversations_counselor", "counselor_user_id", "status", "started_at"),
        Index("idx_conversations_retention", "status", "closed_at", "messages_purged_at"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="chk_conversations_status"),
        CheckConstraint(
            "conversation_type IN ('GENERAL', 'APPOINTMENT', 'SOS')",
            name="chk_conversations_type",
        ),
        CheckConstraint(
            "(status = 'OPEN' AND closed_at IS NULL AND messages_purged_at IS NULL) "
            "OR (status = 'CLOSED' AND closed_at IS NOT NULL "
            "AND (messages_purged_at IS NULL OR messages_purged_at >= closed_at))",
            name="chk_conversations_lifecycle",
        ),
    )

    conversation_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_conversations_student", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    counselor_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_conversations_counselor", ondelete="SET NULL", onupdate="CASCADE"),
    )
    conversation_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="GENERAL")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="OPEN")
    started_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    closed_at: Mapped[object | None] = mapped_column(DATETIME6)
    messages_purged_at: Mapped[object | None] = mapped_column(DATETIME6)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "client_message_id", name="uq_messages_client_id"),
        Index("idx_messages_conversation_time", "conversation_id", "sent_at"),
        Index("idx_messages_sender", "sender_user_id", "sent_at"),
    )

    message_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("conversations.conversation_id", name="fk_messages_conversation", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    sender_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_messages_sender", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    client_message_id: Mapped[str | None] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
