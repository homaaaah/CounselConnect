"""Enforce one pending registration correction per Student.

Revision ID: 20261025_pending_correction
Revises: 20261025_account_screening_scope

Stop application writers before upgrade/downgrade: MySQL DDL commits
independently. Refuse ambiguous existing data; never auto-decide requests.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20261025_pending_correction"
down_revision = "20261025_account_screening_scope"
branch_labels = None
depends_on = None

TABLE = "profile_change_requests"
COLUMN = "pending_student_user_id"
CONSTRAINT = "uq_profile_change_requests_pending_student"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT student_user_id FROM profile_change_requests WHERE status = 'PENDING' "
        "GROUP BY student_user_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first():
        raise RuntimeError(
            "Pending correction guard upgrade refused: duplicate pending requests exist. "
            "Resolve them through an approved review before retrying; no requests were changed."
        )
    # A virtual expression derives existing state; no historical values,
    # submission versions, statuses, or decisions are backfilled.
    if COLUMN not in {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(
            COLUMN, mysql.BIGINT(unsigned=True),
            sa.Computed("CASE WHEN status = 'PENDING' THEN student_user_id ELSE NULL END", persisted=False),
            nullable=True,
        ))
    if CONSTRAINT not in {c["name"] for c in sa.inspect(bind).get_unique_constraints(TABLE)}:
        op.create_unique_constraint(CONSTRAINT, TABLE, [COLUMN])


def downgrade() -> None:
    # Only the constraint and its derived column are removed. Requests,
    # snapshots, decisions and account state remain unchanged.
    bind = op.get_bind()
    if CONSTRAINT in {c["name"] for c in sa.inspect(bind).get_unique_constraints(TABLE)}:
        op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
    if COLUMN in {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}:
        op.drop_column(TABLE, COLUMN)
