"""assistant service: authorization + grounding rules.

Core rules (docs/VIRTUAL_GUIDANCE_ASSISTANT.md):
- Answer ONLY from approved system navigation guidance, current approved
  FAQ content, and PUBLISHED wellness resource metadata + canonical links.
- Clinical, confidential, unsupported, or unknown requests get a bounded
  limitation response — never a diagnosis or medical recommendation.
- No persistent assistant conversation history (not created unless approved).

# TODO: Provider/model integration pending ADR-P08.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.assistant.repository import AssistantRepository


class AssistantService:
    """Bounded virtual guidance assistant rules."""

    def __init__(self, session: Session) -> None:
        self.repository = AssistantRepository(session)


def get_assistant_service(session: Session = Depends(get_session)) -> AssistantService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return AssistantService(session)
