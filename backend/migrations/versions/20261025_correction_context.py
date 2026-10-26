"""Add nullable correction version, snapshot, and evidence context.

Revision ID: 20261025_correction_context
Revises: 20261024_weekly_sched_softdel

Do not reconstruct historical values or requests. Existing services continue
writing legacy-shaped rows until the submission workflow is extended.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20261025_correction_context"
down_revision = "20261024_weekly_sched_softdel"
branch_labels = None
depends_on = None

TABLE = "profile_change_requests"
DATETIME6 = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
NEW_COLUMNS = (
    "submission_version", "previous_change_request_id", "root_change_request_id",
    "extracted_values_json", "registered_values_json", "registered_cor_screening_id",
    "evidence_file_id", "evidence_sha256_hash", "evidence_uploaded_at", "evidence_expires_at",
)


def upgrade() -> None:
    # MySQL DDL commits independently: inspect each object so interrupted
    # additive upgrades can be retried without changing existing records.
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}
    additions = (
        sa.Column("submission_version", mysql.INTEGER(unsigned=True), nullable=True),
        sa.Column("previous_change_request_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("root_change_request_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("extracted_values_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("registered_values_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("registered_cor_screening_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("evidence_file_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("evidence_sha256_hash", sa.BINARY(32), nullable=True),
        sa.Column("evidence_uploaded_at", DATETIME6, nullable=True),
        sa.Column("evidence_expires_at", DATETIME6, nullable=True),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column(TABLE, column)

    foreign_keys = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(TABLE)}
    for name, column, target in (
        ("fk_profile_change_requests_previous", "previous_change_request_id", TABLE),
        ("fk_profile_change_requests_root", "root_change_request_id", TABLE),
        ("fk_profile_change_requests_registered_cor", "registered_cor_screening_id", "cor_screenings"),
    ):
        if name not in foreign_keys:
            op.create_foreign_key(name, TABLE, target,
                                  [column], ["change_request_id" if target == TABLE else "cor_screening_id"],
                                  ondelete="RESTRICT", onupdate="RESTRICT")

    unique = {c["name"] for c in sa.inspect(bind).get_unique_constraints(TABLE)}
    for name, keys in (
        ("uq_profile_change_requests_previous", ["previous_change_request_id"]),
        ("uq_profile_change_requests_version", ["root_change_request_id", "submission_version"]),
    ):
        if name not in unique:
            op.create_unique_constraint(name, TABLE, keys)

    checks = {c["name"]: c["sqltext"] for c in sa.inspect(bind).get_check_constraints(TABLE)}
    status_name = "chk_profile_change_requests_status"
    if status_name in checks and "RETURNED" not in checks[status_name]:
        op.drop_constraint(status_name, TABLE, type_="check")
        del checks[status_name]
    for name, condition in (
        (status_name, "status IN ('PENDING', 'APPROVED', 'REJECTED', 'RETURNED')"),
        ("chk_profile_change_requests_version", "submission_version IS NULL OR submission_version >= 1"),
        ("chk_profile_change_requests_evidence_time",
         "evidence_uploaded_at IS NULL OR evidence_expires_at IS NULL OR evidence_expires_at > evidence_uploaded_at"),
    ):
        if name not in checks:
            op.create_check_constraint(name, TABLE, condition)


def downgrade() -> None:
    # Deployment must stop writers before migration. Refuse lossy rollback;
    # do not erase metadata or convert RETURNED to a fabricated old decision.
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}
    conditions = [f"`{name}` IS NOT NULL" for name in NEW_COLUMNS if name in columns]
    conditions.append("status = 'RETURNED'")
    if bind.execute(sa.text(f"SELECT 1 FROM {TABLE} WHERE " + " OR ".join(conditions) + " LIMIT 1")).first():
        raise RuntimeError("Correction context downgrade refused: preserve versioned data before rollback.")

    checks = {c["name"] for c in sa.inspect(bind).get_check_constraints(TABLE)}
    for name in ("chk_profile_change_requests_version", "chk_profile_change_requests_evidence_time",
                 "chk_profile_change_requests_status"):
        if name in checks:
            op.drop_constraint(name, TABLE, type_="check")
    op.create_check_constraint("chk_profile_change_requests_status", TABLE,
                               "status IN ('PENDING', 'APPROVED', 'REJECTED')")
    foreign_keys = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(TABLE)}
    for name in ("fk_profile_change_requests_previous", "fk_profile_change_requests_root",
                 "fk_profile_change_requests_registered_cor"):
        if name in foreign_keys:
            op.drop_constraint(name, TABLE, type_="foreignkey")
    unique = {c["name"] for c in sa.inspect(bind).get_unique_constraints(TABLE)}
    for name in ("uq_profile_change_requests_previous", "uq_profile_change_requests_version"):
        if name in unique:
            op.drop_constraint(name, TABLE, type_="unique")
    for name in reversed(NEW_COLUMNS):
        if name in columns:
            op.drop_column(TABLE, name)
