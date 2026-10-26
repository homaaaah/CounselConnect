"""store ordered Student-stated concern tags on appointments

Revision ID: 20261026_appointment_concerns
Revises: 20261025_session_records
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20261026_appointment_concerns"
down_revision = "20261025_session_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("appointments")}
    if "concern_categories" not in columns:
        op.add_column(
            "appointments",
            sa.Column("concern_categories", mysql.JSON(), nullable=True),
        )
    if "concern_details" not in columns:
        op.add_column(
            "appointments",
            sa.Column("concern_details", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("appointments")}
    if "concern_details" in columns:
        op.drop_column("appointments", "concern_details")
    if "concern_categories" in columns:
        op.drop_column("appointments", "concern_categories")
