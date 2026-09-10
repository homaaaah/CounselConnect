"""auth ORM model: user_sessions.

Revocable opaque login-session storage. The raw session credential and the
session-bound CSRF token are NEVER stored — only their SHA-256 digests
(BINARY(32)). The table exists to make ADR-P01 sessions possible; login,
cookie transport, and CSRF verification remain unimplemented until that
decision is approved.

FK behavior: ON DELETE CASCADE — a session is an ephemeral credential, not
user history, so deleting an account must never be blocked by stale
sessions (matches student_profiles; audit_events keeps history via SET NULL
because it IS the durable record).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, BINARY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, utcnow

SHA256_BYTES = 32  # BINARY(32) — fixed-length SHA-256 digest


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        # Active-session lookup by user (auth check: find caller's live sessions).
        Index("idx_user_sessions_user_active", "user_id", "revoked_at", "absolute_expires_at"),
        # Cleanup scan: expired or revoked sessions eligible for deletion.
        Index("idx_user_sessions_cleanup", "absolute_expires_at", "revoked_at"),
        CheckConstraint(
            "last_activity_at >= created_at AND absolute_expires_at >= last_activity_at",
            name="chk_user_sessions_timeline",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason IS NULL) "
            "OR (revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="chk_user_sessions_revocation_shape",
        ),
    )

    session_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_user_sessions_user", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    # SHA-256 digests only; raw credentials never persisted (docs/SECURITY.md).
    token_hash: Mapped[bytes] = mapped_column(BINARY(SHA256_BYTES), nullable=False)
    csrf_token_hash: Mapped[bytes] = mapped_column(BINARY(SHA256_BYTES), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, insert_default=utcnow)
    # Explicit genuine-user activity only; never renewed by heartbeats/polls.
    last_activity_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, insert_default=utcnow)
    # Hard ceiling; never slides or extends (12-hour policy, docs/SECURITY.md).
    absolute_expires_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME6)
    revocation_reason: Mapped[str | None] = mapped_column(String(50))
