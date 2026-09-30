"""add SUPERADMIN role to users.role_code

ADR-030 introduces the Superadmin recovery role (process flow): it handles
account recovery and operational exceptions and does not declare a COR
authentic. Widens the existing `chk_users_role` CHECK.
"""

from alembic import op


revision = "20260930_superadmin_role"
down_revision = "20260930_extracted_validity"
branch_labels = None
depends_on = None

_ROLES = "role_code IN ('STUDENT', 'GUIDANCE_STAFF', 'COUNSELOR', 'SUPERADMIN')"
_ROLES_PREVIOUS = "role_code IN ('STUDENT', 'GUIDANCE_STAFF', 'COUNSELOR')"


def upgrade() -> None:
    op.drop_constraint("chk_users_role", "users", type_="check")
    op.create_check_constraint("chk_users_role", "users", _ROLES)


def downgrade() -> None:
    op.drop_constraint("chk_users_role", "users", type_="check")
    op.create_check_constraint("chk_users_role", "users", _ROLES_PREVIOUS)
