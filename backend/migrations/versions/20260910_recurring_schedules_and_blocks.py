"""add counselor recurring schedules and temporary availability blocks

Revision ID: 20260910_recurring_schedules
Revises: 20260909_blocked_dates
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260910_recurring_schedules"
down_revision = "20260909_blocked_dates"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)")),
    )


def upgrade():
    op.create_table(
        "counselor_weekly_schedules",
        sa.Column("weekly_schedule_id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("counselor_user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("campus_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("day_of_week", mysql.TINYINT(unsigned=True), nullable=False),
        sa.Column("start_time", mysql.TIME(), nullable=False),
        sa.Column("end_time", mysql.TIME(), nullable=False),
        sa.Column("slot_duration_minutes", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("delivery_mode", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        *_timestamps(),
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="chk_weekly_schedule_day"),
        sa.CheckConstraint("end_time > start_time", name="chk_weekly_schedule_time"),
        sa.CheckConstraint("slot_duration_minutes BETWEEN 15 AND 240", name="chk_weekly_schedule_duration"),
        sa.CheckConstraint("delivery_mode IN ('ONLINE', 'FACE_TO_FACE', 'BOTH')", name="chk_weekly_schedule_delivery_mode"),
        sa.ForeignKeyConstraint(["counselor_user_id"], ["users.user_id"], name="fk_weekly_schedules_counselor", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.campus_id"], name="fk_weekly_schedules_campus", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("counselor_user_id", "campus_id", "day_of_week", "start_time", "end_time", "slot_duration_minutes", "delivery_mode", name="uq_weekly_schedule_period"),
    )
    op.create_index("idx_weekly_schedule_lookup", "counselor_weekly_schedules", ["counselor_user_id", "day_of_week", "campus_id", "is_active"], unique=False)

    op.create_table(
        "counselor_availability_blocks",
        sa.Column("availability_block_id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("counselor_user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("starts_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("ends_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("is_all_day", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("reason", sa.String(255), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name="chk_availability_block_time"),
        sa.ForeignKeyConstraint(["counselor_user_id"], ["users.user_id"], name="fk_availability_blocks_counselor", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("counselor_user_id", "starts_at", "ends_at", "is_all_day", name="uq_availability_block_period"),
    )
    op.create_index("idx_availability_blocks_overlap", "counselor_availability_blocks", ["counselor_user_id", "starts_at", "ends_at"], unique=False)

    op.add_column("availability_slots", sa.Column("weekly_schedule_id", mysql.BIGINT(unsigned=True), nullable=True))
    op.create_index("idx_availability_weekly_schedule", "availability_slots", ["weekly_schedule_id"], unique=False)
    op.create_foreign_key("fk_availability_weekly_schedule", "availability_slots", "counselor_weekly_schedules", ["weekly_schedule_id"], ["weekly_schedule_id"], ondelete="RESTRICT", onupdate="CASCADE")


def downgrade():
    op.drop_constraint("fk_availability_weekly_schedule", "availability_slots", type_="foreignkey")
    op.drop_index("idx_availability_weekly_schedule", table_name="availability_slots")
    op.drop_column("availability_slots", "weekly_schedule_id")
    op.drop_table("counselor_availability_blocks")
    op.drop_table("counselor_weekly_schedules")
