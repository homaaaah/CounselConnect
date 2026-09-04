"""messaging service: authorization + business rules.

Core rules (docs/REAL_TIME_MESSAGING.md, ARCHITECTURE.md):
- One Student <-> one Counselor per conversation; GENERAL, APPOINTMENT, and
  SOS types with distinct entry authorization.
- Only participants recorded on an OPEN conversation may exchange messages.
- Message bodies are purged 30 days after closure; only permitted
  conversation metadata remains.
- Appointments/SOS modules request conversations through THIS service
  (service contract), never by creating records directly.

# TODO: Real-time transport (WebSocket vs polling) is pending ADR-P02.
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


def get_messaging_service(session: Session = Depends(get_session)) -> MessagingService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return MessagingService(session)
