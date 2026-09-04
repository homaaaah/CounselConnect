"""content service: authorization + business rules.

Core rules (docs/CONTENT_MANAGEMENT.md):
- Counselor-only editing/publication of CMS blocks, FAQs, announcements,
  and structured emergency contacts (write paths arrive with ADR-P01).
- Public/student reads see PUBLISHED content and ACTIVE contacts only
  (DFD D8/P73/P74, discovery search rule 5.6).
- Content is validated and sanitized; it can never alter code, permissions,
  secrets, configuration, or AI instructions.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.content.models import ContentItem
from app.modules.content.repository import ContentRepository


class ContentService(BaseService[ContentItem]):
    """CMS/announcement/emergency-contact business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(ContentRepository(session))

    # --- public reads (landing page, FAQ, SOS fallback) ----------------

    def list_published(self, content_type: str) -> list[ContentItem]:
        return self.repository.list_published(content_type)

    def list_active_emergency_contacts(self):
        return self.repository.list_active_emergency_contacts()


def get_content_service(session: Session = Depends(get_session)) -> ContentService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return ContentService(session)
