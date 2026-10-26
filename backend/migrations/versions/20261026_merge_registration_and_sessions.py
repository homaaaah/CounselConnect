"""Merge registration-correction and appointment/session migration heads."""

revision = "20261026_merge_reg_sessions"
down_revision = ("20261026_appointment_concerns", "20261025_pending_correction")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
