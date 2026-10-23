"""soft delete counselor weekly schedules

Revision ID: 20261024_weekly_sched_softdel
Revises: 20261002_profile_change_requests
"""

from alembic import op
import sqlalchemy as sa


revision = "20261024_weekly_sched_softdel"
down_revision = "20261002_profile_change_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL commits DDL independently of Alembic's version update. Guard the
    # additive column so a retry after an interrupted upgrade is safe.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("counselor_weekly_schedules")}
    if "is_deleted" not in columns:
        op.add_column(
            "counselor_weekly_schedules",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("counselor_weekly_schedules")}
    if "is_deleted" in columns:
        op.drop_column("counselor_weekly_schedules", "is_deleted")
