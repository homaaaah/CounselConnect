"""messaging service: authorization + business rules.

Core rules (docs/REAL_TIME_MESSAGING.md, ARCHITECTURE.md):
- One Student <-> one Counselor per conversation; GENERAL, APPOINTMENT, and
  SOS types with distinct entry authorization.
- Only participants recorded on an OPEN conversation may exchange messages.
- Message bodies are purged 30 days after closure; only permitted
  conversation metadata remains.
- Appointments/SOS modules request conversations through THIS service
  (service contract), never by creating records directly.

# Real-time transport is native WebSocket per ADR-022 (implementation pending).
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.messaging.models import Conversation
from app.modules.messaging.repository import MessagingRepository


class MessagingService(BaseService[Conversation]):
    """Real-time messaging business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(MessagingRepository(session))

    def close_for_appointment(self, appointment):
        """Internal call after the appointment service locks and authorizes the outcome."""
        from datetime import datetime, timezone
        from app.core.exceptions import AppError
        conversation = self.repository.lock_conversation(appointment.conversation_id)
        if (conversation is None or conversation.conversation_type != "APPOINTMENT"
            or appointment.appointment_mode != "ONLINE"
            or conversation.student_user_id != appointment.student_user_id
            or conversation.counselor_user_id != appointment.counselor_user_id):
            raise AppError("CONVERSATION_MISMATCH", "The appointment session link is invalid.")
        if conversation.status == "OPEN":
            conversation.status = "CLOSED"
            conversation.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)


def get_messaging_service(session: Session = Depends(get_session)) -> MessagingService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return MessagingService(session)
