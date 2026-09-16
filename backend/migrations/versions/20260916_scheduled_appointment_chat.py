"""add scheduled appointment chat lifecycle fields

Revision ID: 20260916_scheduled_chat
Revises: 20260910_recurring_schedules
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260916_scheduled_chat"
down_revision = "20260910_recurring_schedules"
branch_labels = None
depends_on = None


def _scalar(sql: str):
    return op.get_bind().execute(sa.text(sql)).scalar()


def upgrade():
    # Validate legacy links before introducing the reverse FK. Diagnostics
    # deliberately expose counts only, never participant or message content.
    inconsistent = _scalar(
        """
        SELECT COUNT(*)
        FROM appointments a
        JOIN conversations c ON c.conversation_id = a.conversation_id
        WHERE c.conversation_type <> 'APPOINTMENT'
           OR c.student_user_id <> a.student_user_id
           OR c.counselor_user_id <> a.counselor_user_id
           OR a.appointment_mode <> 'ONLINE'
        """
    )
    if inconsistent:
        raise RuntimeError(f"scheduled chat migration found {inconsistent} inconsistent appointment link(s)")

    op.add_column("appointments", sa.Column("student_reminder_dispatched_at", mysql.DATETIME(fsp=6), nullable=True))
    op.add_column("appointments", sa.Column("counselor_reminder_dispatched_at", mysql.DATETIME(fsp=6), nullable=True))

    op.add_column("conversations", sa.Column("appointment_id", mysql.BIGINT(unsigned=True), nullable=True))
    op.add_column("conversations", sa.Column("student_joined_at", mysql.DATETIME(fsp=6), nullable=True))
    op.add_column("conversations", sa.Column("counselor_joined_at", mysql.DATETIME(fsp=6), nullable=True))
    op.add_column("conversations", sa.Column("closure_reason", sa.String(32), nullable=True))
    op.add_column("conversations", sa.Column("last_sequence_number", mysql.BIGINT(unsigned=True), nullable=False, server_default=sa.text("0")))
    op.add_column("messages", sa.Column("sequence_number", mysql.BIGINT(unsigned=True), nullable=True))

    op.execute(sa.text("UPDATE conversations c JOIN appointments a ON a.conversation_id = c.conversation_id SET c.appointment_id = a.appointment_id"))
    op.execute(sa.text(
        """
        UPDATE messages m
        JOIN (
            SELECT message_id,
                   ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY sent_at, message_id) AS seq
            FROM messages
        ) ranked ON ranked.message_id = m.message_id
        SET m.sequence_number = ranked.seq
        """
    ))
    op.execute(sa.text(
        """
        UPDATE conversations c
        LEFT JOIN (
            SELECT conversation_id, MAX(sequence_number) AS max_seq
            FROM messages GROUP BY conversation_id
        ) m ON m.conversation_id = c.conversation_id
        SET c.last_sequence_number = COALESCE(m.max_seq, 0)
        """
    ))

    op.alter_column("messages", "sequence_number", existing_type=mysql.BIGINT(unsigned=True), nullable=False)
    op.create_unique_constraint("uq_conversations_appointment", "conversations", ["appointment_id"])
    op.create_foreign_key("fk_conversations_appointment", "conversations", "appointments", ["appointment_id"], ["appointment_id"], ondelete="RESTRICT", onupdate="CASCADE")
    op.create_unique_constraint("uq_messages_sequence", "messages", ["conversation_id", "sequence_number"])


def downgrade():
    op.drop_constraint("uq_messages_sequence", "messages", type_="unique")
    op.drop_constraint("fk_conversations_appointment", "conversations", type_="foreignkey")
    op.drop_constraint("uq_conversations_appointment", "conversations", type_="unique")
    op.drop_column("messages", "sequence_number")
    op.drop_column("conversations", "last_sequence_number")
    op.drop_column("conversations", "closure_reason")
    op.drop_column("conversations", "counselor_joined_at")
    op.drop_column("conversations", "student_joined_at")
    op.drop_column("conversations", "appointment_id")
    op.drop_column("appointments", "counselor_reminder_dispatched_at")
    op.drop_column("appointments", "student_reminder_dispatched_at")
