"""Add independent account deactivation and COR screening purpose.

Revision ID: 20261025_account_screening_scope
Revises: 20261025_correction_context

Schema foundations only: no account is deactivated and no correction-only
screening is created. Existing account statuses and screening results stay intact.
Stop application writers before upgrade/downgrade (MySQL DDL implicitly commits).
"""

from alembic import op
import sqlalchemy as sa

revision = "20261025_account_screening_scope"
down_revision = "20261025_correction_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "is_deactivated" not in {c["name"] for c in sa.inspect(bind).get_columns("users")}:
        op.add_column("users", sa.Column("is_deactivated", sa.Boolean(), nullable=False,
                                       server_default=sa.text("FALSE")))
    if "purpose" not in {c["name"] for c in sa.inspect(bind).get_columns("cor_screenings")}:
        op.add_column("cor_screenings", sa.Column("purpose", sa.String(20), nullable=False,
                                                server_default="REGISTRATION"))
    for table, name, condition in (
        ("users", "chk_users_is_deactivated", "is_deactivated IN (0, 1)"),
        ("cor_screenings", "chk_cor_screenings_purpose", "purpose IN ('REGISTRATION', 'CORRECTION')"),
    ):
        if name not in {c["name"] for c in sa.inspect(bind).get_check_constraints(table)}:
            op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    bind = op.get_bind()
    user_columns = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    screening_columns = {c["name"] for c in sa.inspect(bind).get_columns("cor_screenings")}
    # Preflight BOTH tables before any DDL: rollback must not silently reactivate
    # a disabled account or turn review-only evidence into enrollment evidence.
    if "is_deactivated" in user_columns and bind.execute(
        sa.text("SELECT 1 FROM users WHERE is_deactivated <> 0 LIMIT 1")
    ).first():
        raise RuntimeError("Account/screening scope downgrade refused: deactivated accounts exist.")
    if "purpose" in screening_columns and bind.execute(
        sa.text("SELECT 1 FROM cor_screenings WHERE purpose <> 'REGISTRATION' LIMIT 1")
    ).first():
        raise RuntimeError("Account/screening scope downgrade refused: correction-only screenings exist.")

    for table, column, name, columns in (
        ("cor_screenings", "purpose", "chk_cor_screenings_purpose", screening_columns),
        ("users", "is_deactivated", "chk_users_is_deactivated", user_columns),
    ):
        if name in {c["name"] for c in sa.inspect(bind).get_check_constraints(table)}:
            op.drop_constraint(name, table, type_="check")
        if column in columns:
            op.drop_column(table, column)
