"""profile_change ORM model: Student-requested profile edits (ADR-032)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class ProfileChangeRequest(Base):
    """A Student's requested correction to names/year_level/section.

    `PENDING` until a Superadmin approves or rejects it. The Student's account
    is already active; approving applies the requested values to the profile.
    """

    __tablename__ = "profile_change_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="chk_profile_change_requests_status",
        ),
        Index("idx_profile_change_requests_status", "status"),
        Index("idx_profile_change_requests_student", "student_user_id"),
    )

    change_request_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    student_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.user_id",
            name="fk_profile_change_requests_student",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    cor_screening_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "cor_screenings.cor_screening_id",
            name="fk_profile_change_requests_screening",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    requested_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_middle_name: Mapped[str | None] = mapped_column(String(100))
    requested_last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_year_level: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    requested_section: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.user_id",
            name="fk_profile_change_requests_reviewer",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME6)
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow
    )
