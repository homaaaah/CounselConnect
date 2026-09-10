"""messaging repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.messaging.models import Conversation, Message


class MessagingRepository(BaseRepository[Conversation]):
    """Owns all conversation/message SQLAlchemy queries."""

    model = Conversation

    def lock_conversation(self, conversation_id):
        return self.session.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id)
            .with_for_update().execution_options(populate_existing=True))

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

    def list_closed_conversations_purge_due(self, purge_cutoff) -> list[Conversation]:
        """Closed conversations whose 30-day message retention has elapsed."""
        return list(
            self.session.scalars(
                select(Conversation).where(
                    Conversation.status == "CLOSED",
                    Conversation.closed_at.is_not(None),
                    Conversation.closed_at < purge_cutoff,
                    Conversation.messages_purged_at.is_(None),
                )
            )
        )
