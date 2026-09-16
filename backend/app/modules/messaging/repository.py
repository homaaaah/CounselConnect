"""messaging repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.modules.bases import BaseRepository
from app.modules.messaging.models import Conversation, Message


class MessagingRepository(BaseRepository[Conversation]):
    """Owns all conversation/message SQLAlchemy queries."""

    model = Conversation

    def lock_conversation(self, conversation_id):
        return self.session.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id)
            .with_for_update().execution_options(populate_existing=True))

    def conversation_by_appointment(self, appointment_id, *, lock=False):
        stmt = select(Conversation).where(Conversation.appointment_id == appointment_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(stmt)

    def find_message_by_client_id(self, conversation_id, client_message_id):
        return self.session.scalar(select(Message).where(
            Message.conversation_id == conversation_id,
            Message.client_message_id == client_message_id,
        ))

    def message_count(self, conversation_id):
        return self.session.scalar(select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        ))

    def find_message(self, message_id: int) -> Message | None:
        return self.session.get(Message, message_id)

    def list_messages(self, conversation_id: int) -> list[Message]:
        return list(
            self.session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.sent_at.asc())
            )
        )

    def message_history(self, conversation_id, *, before_sequence=None, after_sequence=None, limit=50):
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if before_sequence is not None:
            stmt = stmt.where(Message.sequence_number < before_sequence)
        if after_sequence is not None:
            stmt = stmt.where(Message.sequence_number > after_sequence)
        if after_sequence is not None:
            rows = list(self.session.scalars(stmt.order_by(Message.sequence_number).limit(limit + 1)))
            return rows[:limit], len(rows) > limit
        rows = list(self.session.scalars(stmt.order_by(Message.sequence_number.desc()).limit(limit + 1)))
        has_more = len(rows) > limit
        return list(reversed(rows[:limit])), has_more

    def list_closed_conversations_purge_due(self, purge_cutoff) -> list[Conversation]:
        """Closed conversations whose 30-day message retention has elapsed."""
        return list(
            self.session.scalars(
                select(Conversation).where(
                    Conversation.status == "CLOSED",
                    Conversation.closed_at.is_not(None),
                    Conversation.closed_at <= purge_cutoff,
                    Conversation.messages_purged_at.is_(None),
                )
            )
        )

    def delete_messages(self, conversation_id):
        return self.session.execute(
            delete(Message).where(Message.conversation_id == conversation_id)
        ).rowcount
