"""add one-time COR verification token to cor_screenings

Registration no longer signs the Student in. Instead the registration response
returns a one-time verification token that authorizes confirm/reject/re-upload
for that screening only. The raw token is never stored: only its SHA-256
digest (BINARY(32)) and issue time are persisted, mirroring user_sessions.

Revision ID: 20261001_cor_verification_token
Revises: 20260930_superadmin_role
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20261001_cor_verification_token"
down_revision = "20260930_superadmin_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cor_screenings", sa.Column("verification_token_hash", sa.BINARY(length=32), nullable=True)
    )
    op.add_column(
        "cor_screenings",
        sa.Column(
            "verification_token_issued_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_cor_screenings_token", "cor_screenings", ["verification_token_hash"]
    )


def downgrade() -> None:
    op.drop_index("idx_cor_screenings_token", table_name="cor_screenings")
    op.drop_column("cor_screenings", "verification_token_issued_at")
    op.drop_column("cor_screenings", "verification_token_hash")
