"""content repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.content.models import ContentItem, EmergencyContact


class ContentRepository(BaseRepository[ContentItem]):
    """Owns all CMS/emergency-contact SQLAlchemy queries."""

    model = ContentItem

    def list_published(self, content_type: str) -> list[ContentItem]:
        """Published items of one type, newest first.

        DFD 5.6/P56 rule: only PUBLISHED content is ever student/public facing.
        """
        return list(
            self.session.scalars(
                select(ContentItem)
                .where(
                    ContentItem.content_type == content_type,
                    ContentItem.is_published.is_(True),
                )
                .order_by(ContentItem.updated_at.desc())
            )
        )

    def list_active_emergency_contacts(self) -> list[EmergencyContact]:
        """Ordered active contacts for the SOS fallback display (DFD 4.6)."""
        return list(
            self.session.scalars(
                select(EmergencyContact)
                .where(EmergencyContact.is_active.is_(True))
                .order_by(EmergencyContact.display_order.asc())
            )
        )
