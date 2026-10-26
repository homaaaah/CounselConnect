"""profile_change ORM model: Student-requested profile edits (ADR-032)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BINARY, JSON, CheckConstraint, Computed, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT, utcnow


class ProfileChangeRequest(Base):
    """A Student's requested correction to names/year_level/section.

    The nullable version/snapshot fields are unknown on legacy rows. Initial
    registration submissions now record version 1 and immutable context.
    """

    __tablename__ = "profile_change_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'RETURNED')",
            name="chk_profile_change_requests_status",
        ),
        Index("idx_profile_change_requests_status", "status"),
        Index("idx_profile_change_requests_student", "student_user_id"),
        UniqueConstraint("pending_student_user_id", name="uq_profile_change_requests_pending_student"),
        UniqueConstraint("previous_change_request_id", name="uq_profile_change_requests_previous"),
        UniqueConstraint(
            "root_change_request_id", "submission_version",
            name="uq_profile_change_requests_version",
        ),
        CheckConstraint(
            "submission_version IS NULL OR submission_version >= 1",
            name="chk_profile_change_requests_version",
        ),
        CheckConstraint(
            "evidence_uploaded_at IS NULL OR evidence_expires_at IS NULL "
            "OR evidence_expires_at > evidence_uploaded_at",
            name="chk_profile_change_requests_evidence_time",
        ),
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
    # Constraint-only derived value, never supplied by callers or needed by DTOs.
    # VIRTUAL preserves the existing owner FK's CASCADE actions on MySQL.
    pending_student_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        Computed("CASE WHEN status = 'PENDING' THEN student_user_id ELSE NULL END", persisted=False),
        deferred=True,
    )
    submission_version: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    # First version has no predecessor/root pointer; its own ID is the root.
    # Descendants point to that root, including when it is a legacy row.
    previous_change_request_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("profile_change_requests.change_request_id",
                   name="fk_profile_change_requests_previous", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    root_change_request_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("profile_change_requests.change_request_id",
                   name="fk_profile_change_requests_root", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    extracted_values_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    registered_values_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    registered_cor_screening_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("cor_screenings.cor_screening_id",
                   name="fk_profile_change_requests_registered_cor", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    # Historical opaque file ID intentionally has no FK: cleanup deletes the
    # temporary file metadata, but must not erase the submitted evidence identity.
    evidence_file_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    evidence_sha256_hash: Mapped[bytes | None] = mapped_column(BINARY(32))
    evidence_uploaded_at: Mapped[datetime | None] = mapped_column(DATETIME6)
    evidence_expires_at: Mapped[datetime | None] = mapped_column(DATETIME6)
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
