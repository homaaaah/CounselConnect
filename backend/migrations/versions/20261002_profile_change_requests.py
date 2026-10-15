"""add profile_change_requests for student-requested profile edits

Students may request edits to names/year_level/section during registration
verification (never student_number, academic_period, campus, program). The
account activates with the COR-verified values; the requested changes are
approved or rejected by a Superadmin (ADR-032).

Revision ID: 20261002_profile_change_requests
Revises: 20261001_cor_verification_token
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20261002_profile_change_requests"
down_revision = "20261001_cor_verification_token"
branch_labels = None
depends_on = None

DATETIME6 = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "profile_change_requests",
        sa.Column("change_request_id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("student_user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("cor_screening_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("requested_first_name", sa.String(length=100), nullable=False),
        sa.Column("requested_middle_name", sa.String(length=100), nullable=True),
        sa.Column("requested_last_name", sa.String(length=100), nullable=False),
        sa.Column("requested_year_level", mysql.TINYINT(unsigned=True), nullable=False),
        sa.Column("requested_section", sa.String(length=50), nullable=False),
        sa.Column("reviewed_by_user_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("reviewed_at", DATETIME6, nullable=True),
        sa.Column("decision_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.ForeignKeyConstraint(
            ["student_user_id"], ["users.user_id"],
            name="fk_profile_change_requests_student",
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cor_screening_id"], ["cor_screenings.cor_screening_id"],
            name="fk_profile_change_requests_screening",
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.user_id"],
            name="fk_profile_change_requests_reviewer",
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="chk_profile_change_requests_status",
        ),
    )
    op.create_index(
        "idx_profile_change_requests_status", "profile_change_requests", ["status"]
    )
    op.create_index(
        "idx_profile_change_requests_student", "profile_change_requests", ["student_user_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_profile_change_requests_student", table_name="profile_change_requests")
    op.drop_index("idx_profile_change_requests_status", table_name="profile_change_requests")
    op.drop_table("profile_change_requests")
