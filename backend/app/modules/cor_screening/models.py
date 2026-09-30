"""cor_screening ORM models.

Mirrors the approved v5 automated-screening schema (migration
`20260930_automated_cor_screening`). COR file CONTENT is never stored in
MySQL — only temporary private-storage metadata with cleanup state.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BINARY,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import DATETIME6, TS_DEFAULT


class CorScreening(Base):
    """One automated screening attempt for a Student's COR."""

    __tablename__ = "cor_screenings"
    __table_args__ = (
        Index("idx_cor_screenings_student_status", "student_user_id", "status", "submitted_at"),
        Index("idx_cor_screenings_status_queue", "status", "submitted_at"),
        Index("idx_cor_screenings_validity", "student_user_id", "status", "valid_until"),
        Index("idx_cor_screenings_barcode_status", "barcode_status", "submitted_at"),
        Index("idx_cor_screenings_campus", "extracted_campus_id"),
        Index("idx_cor_screenings_program", "extracted_program_id"),
        CheckConstraint(
            "status IN ('PROCESSING', 'AWAITING_CONFIRMATION', 'PASSED', 'NEEDS_RESUBMISSION', 'FAILED')",
            name="chk_cor_screenings_status",
        ),
        CheckConstraint(
            "format_match_score IS NULL OR format_match_score BETWEEN 0.0000 AND 1.0000",
            name="chk_cor_screenings_format_score",
        ),
        CheckConstraint(
            "extraction_confidence IS NULL OR extraction_confidence BETWEEN 0.0000 AND 1.0000",
            name="chk_cor_screenings_extraction_confidence",
        ),
        CheckConstraint(
            "barcode_status IN ('NOT_PROCESSED', 'NOT_FOUND', 'UNREADABLE', 'INVALID_FORMAT', 'DECODED', 'MISMATCH')",
            name="chk_cor_screenings_barcode_status",
        ),
        CheckConstraint(
            "barcode_decode_confidence IS NULL OR barcode_decode_confidence BETWEEN 0.0000 AND 1.0000",
            name="chk_cor_screenings_barcode_confidence",
        ),
        CheckConstraint(
            "extracted_year_level IS NULL OR extracted_year_level BETWEEN 1 AND 10",
            name="chk_cor_screenings_year",
        ),
        CheckConstraint(
            "(processing_started_at IS NULL OR processing_started_at >= submitted_at) "
            "AND (processed_at IS NULL OR processed_at >= submitted_at) "
            "AND (confirmed_at IS NULL OR confirmed_at >= submitted_at)",
            name="chk_cor_screenings_timeline",
        ),
    )

    cor_screening_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    student_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_cor_screenings_student", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="PROCESSING")
    format_template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    format_match_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    barcode_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="NOT_PROCESSED")
    barcode_symbology: Mapped[str | None] = mapped_column(String(32))
    barcode_decode_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    # SHA-256 digest only; the raw decoded payload is never persisted or logged.
    barcode_payload_hash: Mapped[bytes | None] = mapped_column(BINARY(32))
    barcode_payload_format_valid: Mapped[bool | None] = mapped_column(Boolean)
    barcode_student_number_match: Mapped[bool | None] = mapped_column(Boolean)
    barcode_academic_period_match: Mapped[bool | None] = mapped_column(Boolean)
    failure_reason_code: Mapped[str | None] = mapped_column(String(100))
    # Safe validation codes and scores only; never raw OCR text.
    validation_results_json: Mapped[dict | None] = mapped_column(JSON)
    extracted_student_number: Mapped[str | None] = mapped_column(String(50))
    extracted_first_name: Mapped[str | None] = mapped_column(String(100))
    extracted_middle_name: Mapped[str | None] = mapped_column(String(100))
    extracted_last_name: Mapped[str | None] = mapped_column(String(100))
    extracted_campus_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("campuses.campus_id", name="fk_cor_screenings_campus", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    extracted_program_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("programs.program_id", name="fk_cor_screenings_program", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    extracted_year_level: Mapped[int | None] = mapped_column(TINYINT(unsigned=True))
    extracted_section: Mapped[str | None] = mapped_column(String(50))
    extracted_academic_period: Mapped[str | None] = mapped_column(String(100))
    extracted_valid_until: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    submitted_at: Mapped[datetime] = mapped_column(
        DATETIME6, nullable=False, server_default=TS_DEFAULT
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DATETIME6)
    processed_at: Mapped[datetime | None] = mapped_column(DATETIME6)
    confirmed_at: Mapped[datetime | None] = mapped_column(DATETIME6)


class CorScreeningFile(Base):
    """Temporary private COR storage metadata only (never file content)."""

    __tablename__ = "cor_screening_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_cor_screening_files_storage_key"),
        Index("idx_cor_screening_files_screening", "cor_screening_id"),
        Index("idx_cor_screening_files_cleanup", "cleanup_state", "expires_at"),
        CheckConstraint("size_bytes > 0", name="chk_cor_screening_files_size"),
        CheckConstraint("cleanup_state IN ('PENDING', 'FAILED')", name="chk_cor_screening_files_cleanup_state"),
    )

    cor_screening_file_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    cor_screening_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "cor_screenings.cor_screening_id",
            name="fk_cor_screening_files_screening",
            ondelete="CASCADE",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    sha256_hash: Mapped[bytes] = mapped_column(BINARY(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False)
    cleanup_state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PENDING")
    uploaded_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, server_default=TS_DEFAULT)
