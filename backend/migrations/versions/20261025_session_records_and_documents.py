"""appointment-scoped counseling records and private session documents

Revision ID: 20261025_session_records
Revises: 20261024_weekly_sched_softdel
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20261025_session_records"
down_revision = "20261024_weekly_sched_softdel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL commits DDL independently of Alembic's version row; guard so a
    # retry after an interrupted upgrade is safe.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "session_records" not in existing:
        op.create_table(
            "session_records",
            sa.Column("record_id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("appointment_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("counselor_user_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("notepad", sa.Text(), nullable=True),
            sa.Column("presenting_concern", sa.Text(), nullable=True),
            sa.Column("session_summary", sa.Text(), nullable=True),
            sa.Column("intervention", sa.Text(), nullable=True),
            sa.Column("plan", sa.Text(), nullable=True),
            sa.Column("follow_up_on", mysql.DATE(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'DRAFT'")),
            sa.Column("finalized_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
            sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
            sa.CheckConstraint("status IN ('DRAFT', 'FINAL')", name="chk_session_records_status"),
            sa.ForeignKeyConstraint(
                ["appointment_id"], ["appointments.appointment_id"],
                name="fk_session_records_appointment", ondelete="CASCADE", onupdate="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["counselor_user_id"], ["users.user_id"],
                name="fk_session_records_counselor", ondelete="RESTRICT", onupdate="CASCADE",
            ),
            sa.PrimaryKeyConstraint("record_id"),
            sa.UniqueConstraint("appointment_id", name="uq_session_records_appointment"),
        )
    if "session_documents" not in existing:
        op.create_table(
            "session_documents",
            sa.Column("document_id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("appointment_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("uploader_user_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(64), nullable=False),
            sa.Column("size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("sha256", mysql.BINARY(32), nullable=False),
            sa.Column("storage_key", sa.String(512), nullable=False),
            sa.Column("deleted_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("deleted_by_user_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
            sa.ForeignKeyConstraint(
                ["appointment_id"], ["appointments.appointment_id"],
                name="fk_session_documents_appointment", ondelete="CASCADE", onupdate="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["uploader_user_id"], ["users.user_id"],
                name="fk_session_documents_uploader", ondelete="RESTRICT", onupdate="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["deleted_by_user_id"], ["users.user_id"],
                name="fk_session_documents_deleted_by", ondelete="RESTRICT", onupdate="CASCADE",
            ),
            sa.PrimaryKeyConstraint("document_id"),
            sa.UniqueConstraint("storage_key", name="uq_session_documents_storage_key"),
        )
        op.create_index(
            "idx_session_documents_appointment",
            "session_documents",
            ["appointment_id", "deleted_at"],
        )


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "session_documents" in existing:
        op.drop_table("session_documents")
    if "session_records" in existing:
        op.drop_table("session_records")
