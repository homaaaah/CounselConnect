"""enrollment_verification ORM models.

Mirrors CounselConnect_Initial_Database_v4.sql exactly. COR file CONTENT is
never stored in MySQL — only temporary private-storage metadata with
cleanup state (deleted after decision or the seven-day pending TTL).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class EnrollmentVerification(Base):
    __tablename__ = "enrollment_verifications"
    __table_args__ = (
        Index("idx_verifications_student_status", "student_user_id", "status", "submitted_at"),
        Index("idx_verifications_validity", "student_user_id", "status", "valid_until"),
        Index("idx_verifications_reviewer", "reviewed_by_user_id"),
        Index("idx_verifications_staff_queue", "assigned_guidance_staff_user_id", "status", "submitted_at"),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'NEEDS_RESUBMISSION', 'REJECTED', 'EXPIRED')",
            name="chk_verifications_status",
        ),
        # v4.1: chk_verifications_decision_shape is enforced in the service
        # layer, not DDL (MySQL 8 forbids CHECKs referencing FK-action columns).
    )

    verification_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_verifications_student", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PENDING")
    submitted_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    assigned_guidance_staff_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_verifications_assigned_staff", ondelete="SET NULL", onupdate="CASCADE"),
    )
    decision_at: Mapped[datetime | None] = mapped_column(DATETIME6)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_verifications_reviewer", ondelete="SET NULL", onupdate="CASCADE"),
    )
    reason_code: Mapped[str | None] = mapped_column(String(50))
    reviewer_note: Mapped[str | None] = mapped_column(String(500))
    valid_until: Mapped[date | None] = mapped_column(Date)


class EnrollmentVerificationFile(Base):
    """Temporary private COR storage metadata only (never file content)."""

    __tablename__ = "enrollment_verification_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_verification_files_storage_key"),
        Index("idx_verification_files_verification", "verification_id"),
        Index("idx_verification_files_cleanup", "cleanup_state", "expires_at"),
        CheckConstraint("size_bytes > 0", name="chk_verification_files_size"),
        CheckConstraint(
            "cleanup_state IN ('PENDING', 'FAILED')",
            name="chk_verification_files_cleanup_state",
        ),
    )

    file_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    verification_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("enrollment_verifications.verification_id", name="fk_verification_files_verification", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False)
    cleanup_state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PENDING")
