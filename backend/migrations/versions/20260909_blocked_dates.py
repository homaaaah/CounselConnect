"""add counselor blocked dates for calendar defaults"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20260909_blocked_dates"
down_revision = "297c92da239d"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "counselor_blocked_dates",
        sa.Column("blocked_date_id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("counselor_user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("blocked_date", mysql.DATE(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.ForeignKeyConstraint(["counselor_user_id"], ["users.user_id"], name="fk_blocked_dates_counselor", onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("blocked_date_id", name=op.f("pk_counselor_blocked_dates")),
        sa.UniqueConstraint("counselor_user_id", "blocked_date", name="uq_counselor_blocked_date"),
    )
    op.create_index("idx_counselor_blocked_dates_date", "counselor_blocked_dates", ["blocked_date"], unique=False)

def downgrade():
    op.drop_index("idx_counselor_blocked_dates_date", table_name="counselor_blocked_dates")
    op.drop_constraint("fk_blocked_dates_counselor", "counselor_blocked_dates", type_="foreignkey")
    op.drop_table("counselor_blocked_dates")

