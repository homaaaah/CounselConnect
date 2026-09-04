"""sos ORM models: sos_cases, sos_responses.

Mirrors CounselConnect_Initial_Database_v4.sql exactly (rule-based triage
lifecycle OPEN -> RESPONDED -> CLOSED; keyed five-question responses).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class SosCase(Base):
    __tablename__ = "sos_cases"
    __table_args__ = (
        UniqueConstraint("conversation_id", name="uq_sos_cases_conversation"),
        Index("idx_sos_cases_student", "student_user_id", "status", "submitted_at"),
        Index("idx_sos_cases_counselor", "assigned_counselor_user_id", "status", "submitted_at"),
        CheckConstraint("status IN ('OPEN', 'RESPONDED', 'CLOSED')", name="chk_sos_cases_status"),
        CheckConstraint(
            "(status = 'OPEN' AND responded_at IS NULL AND closed_at IS NULL) "
            "OR (status = 'RESPONDED' AND responded_at IS NOT NULL AND closed_at IS NULL) "
            "OR (status = 'CLOSED' AND responded_at IS NOT NULL AND closed_at IS NOT NULL AND closed_at >= responded_at)",
            name="chk_sos_cases_lifecycle",
        ),
    )

    sos_case_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_sos_cases_student", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    assigned_counselor_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_sos_cases_counselor", ondelete="SET NULL", onupdate="CASCADE"),
    )
    conversation_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("conversations.conversation_id", name="fk_sos_cases_conversation", ondelete="SET NULL", onupdate="CASCADE"),
    )
    instrument_version: Mapped[str] = mapped_column(String(50), nullable=False)
    urgency_result_code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="OPEN")
    submitted_at: Mapped[object] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow)
    responded_at: Mapped[object | None] = mapped_column(DATETIME6)
    closed_at: Mapped[object | None] = mapped_column(DATETIME6)


class SosResponse(Base):
    __tablename__ = "sos_responses"

    sos_case_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sos_cases.sos_case_id", name="fk_sos_responses_case", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    question_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    answer_value: Mapped[str] = mapped_column(String(255), nullable=False)
