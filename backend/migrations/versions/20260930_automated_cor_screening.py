"""add automated COR screening tables

Implements the approved automated COR screening flow (ADR-029): a COR PDF is
screened on upload (format match + OCR extraction + embedded barcode) and the
Student confirms the extracted academic fields, which activates the account.

- cor_screenings: screening result + extracted fields + lifecycle timestamps.
  Raw OCR text and raw barcode payloads are never stored; only codes and
  scores (validation_results_json) and a payload SHA-256 digest.
- cor_screening_files: temporary private-storage metadata only. COR bytes stay
  outside MySQL and are deleted after confirmation/resubmission or the
  seven-day TTL.

Legacy enrollment_verifications tables are intentionally left untouched.

Revision ID: 20260930_automated_cor_screening
Revises: 20260916_scheduled_chat
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260930_automated_cor_screening"
down_revision = "20260916_scheduled_chat"
branch_labels = None
depends_on = None

_SCREENING_STATUSES = (
    "'PROCESSING','AWAITING_CONFIRMATION','PASSED','NEEDS_RESUBMISSION','FAILED'"
)
_BARCODE_STATUSES = "'NOT_PROCESSED','NOT_FOUND','UNREADABLE','INVALID_FORMAT','DECODED','MISMATCH'"


def upgrade() -> None:
    op.create_table(
        "cor_screenings",
        sa.Column("cor_screening_id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("student_user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="PROCESSING"),
        sa.Column("format_template_version", sa.String(length=50), nullable=False),
        sa.Column("format_match_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("barcode_status", sa.String(length=32), nullable=False, server_default="NOT_PROCESSED"),
        sa.Column("barcode_symbology", sa.String(length=32), nullable=True),
        sa.Column("barcode_decode_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("barcode_payload_hash", sa.BINARY(length=32), nullable=True),
        sa.Column("barcode_payload_format_valid", sa.Boolean(), nullable=True),
        sa.Column("barcode_student_number_match", sa.Boolean(), nullable=True),
        sa.Column("barcode_academic_period_match", sa.Boolean(), nullable=True),
        sa.Column("failure_reason_code", sa.String(length=100), nullable=True),
        sa.Column("validation_results_json", sa.JSON(), nullable=True),
        sa.Column("extracted_student_number", sa.String(length=50), nullable=True),
        sa.Column("extracted_first_name", sa.String(length=100), nullable=True),
        sa.Column("extracted_middle_name", sa.String(length=100), nullable=True),
        sa.Column("extracted_last_name", sa.String(length=100), nullable=True),
        sa.Column("extracted_campus_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("extracted_program_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("extracted_year_level", mysql.TINYINT(unsigned=True), nullable=True),
        sa.Column("extracted_section", sa.String(length=50), nullable=True),
        sa.Column("extracted_academic_period", sa.String(length=100), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column(
            "processing_started_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=True,
        ),
        sa.CheckConstraint(f"status IN ({_SCREENING_STATUSES})", name="chk_cor_screenings_status"),
        sa.CheckConstraint(
            "format_match_score IS NULL OR format_match_score BETWEEN 0.0000 AND 1.0000",
            name="chk_cor_screenings_format_score",
        ),
        sa.CheckConstraint(
            "extraction_confidence IS NULL OR extraction_confidence BETWEEN 0.0000 AND 1.0000",
            name="chk_cor_screenings_extraction_confidence",
        ),
        sa.CheckConstraint(f"barcode_status IN ({_BARCODE_STATUSES})", name="chk_cor_screenings_barcode_status"),
        sa.CheckConstraint(
            "barcode_decode_confidence IS NULL OR barcode_decode_confidence BETWEEN 0.0000 AND 1.0000",
            name="chk_cor_screenings_barcode_confidence",
        ),
        sa.CheckConstraint(
            "extracted_year_level IS NULL OR extracted_year_level BETWEEN 1 AND 10",
            name="chk_cor_screenings_year",
        ),
        sa.CheckConstraint(
            "(processing_started_at IS NULL OR processing_started_at >= submitted_at) "
            "AND (processed_at IS NULL OR processed_at >= submitted_at) "
            "AND (confirmed_at IS NULL OR confirmed_at >= submitted_at)",
            name="chk_cor_screenings_timeline",
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"],
            ["users.user_id"],
            name="fk_cor_screenings_student",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extracted_campus_id"],
            ["campuses.campus_id"],
            name="fk_cor_screenings_campus",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extracted_program_id"],
            ["programs.program_id"],
            name="fk_cor_screenings_program",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("cor_screening_id", name="pk_cor_screenings"),
    )
    op.create_index(
        "idx_cor_screenings_student_status", "cor_screenings", ["student_user_id", "status", "submitted_at"]
    )
    op.create_index("idx_cor_screenings_status_queue", "cor_screenings", ["status", "submitted_at"])
    op.create_index(
        "idx_cor_screenings_validity", "cor_screenings", ["student_user_id", "status", "valid_until"]
    )
    op.create_index("idx_cor_screenings_barcode_status", "cor_screenings", ["barcode_status", "submitted_at"])
    op.create_index("idx_cor_screenings_campus", "cor_screenings", ["extracted_campus_id"])
    op.create_index("idx_cor_screenings_program", "cor_screenings", ["extracted_program_id"])

    op.create_table(
        "cor_screening_files",
        sa.Column("cor_screening_file_id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("cor_screening_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sha256_hash", sa.BINARY(length=32), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.Column("cleanup_state", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column(
            "uploaded_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.CheckConstraint("size_bytes > 0", name="chk_cor_screening_files_size"),
        sa.CheckConstraint("cleanup_state IN ('PENDING','FAILED')", name="chk_cor_screening_files_cleanup_state"),
        sa.ForeignKeyConstraint(
            ["cor_screening_id"],
            ["cor_screenings.cor_screening_id"],
            name="fk_cor_screening_files_screening",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("cor_screening_file_id", name="pk_cor_screening_files"),
        sa.UniqueConstraint("storage_key", name="uq_cor_screening_files_storage_key"),
    )
    op.create_index(
        "idx_cor_screening_files_screening", "cor_screening_files", ["cor_screening_id"]
    )
    op.create_index(
        "idx_cor_screening_files_cleanup", "cor_screening_files", ["cleanup_state", "expires_at"]
    )


def downgrade() -> None:
    op.drop_table("cor_screening_files")
    # Drop the FK before the indexes: MySQL error 1553 refuses to drop an
    # index still required by a foreign-key constraint.
    op.drop_constraint("fk_cor_screenings_student", "cor_screenings", type_="foreignkey")
    op.drop_table("cor_screenings")
