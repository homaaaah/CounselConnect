"""add extracted enrollment-validity date to cor_screenings

The process flow extracts enrollment-validity information from the COR when
readable. Stored as a safe structured field; confirmation uses it as the
account validity date when it is a future date, otherwise falls back to a
12-month default.

Revision ID: 20260930_extracted_validity
Revises: 20260930_automated_cor_screening
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_extracted_validity"
down_revision = "20260930_automated_cor_screening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cor_screenings", sa.Column("extracted_valid_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("cor_screenings", "extracted_valid_until")
