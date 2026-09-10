"""wellness_resources service: authorization + business rules.

Core rules (docs/WELLNESS_RESOURCE_DISCOVERY.md, ARCHITECTURE.md):
- Allowlisted trusted sources only; RSS/Atom/structured metadata preferred,
  limited approved scraping fallback.
- Bounded card metadata + canonical links only — NEVER mirrored article
  bodies; normalize + dedupe before saving as PENDING.
- Counselor review is mandatory before PUBLISHED; reject/disable lifecycle.
- Manual internal resources (link/article/file) created by Counselor only.

# TODO: Manual publication rule is pending ADR-P07.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.wellness_resources.models import WellnessResource
from app.modules.wellness_resources.repository import WellnessResourcesRepository


class WellnessResourcesService(BaseService[WellnessResource]):
    """Wellness resource discovery/review/publication business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(WellnessResourcesRepository(session))


def get_wellness_resources_service(
    session: Session = Depends(get_session),
) -> WellnessResourcesService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return WellnessResourcesService(session)
