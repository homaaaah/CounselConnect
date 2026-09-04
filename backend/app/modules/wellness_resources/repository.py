"""wellness_resources repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.wellness_resources.models import (
    ResourceCategory,
    ResourceSource,
    WellnessResource,
    WellnessResourceCategory,
)


class WellnessResourcesRepository(BaseRepository[WellnessResource]):
    """Owns all wellness-resource SQLAlchemy queries."""

    model = WellnessResource

    def find_source(self, source_id: int) -> ResourceSource | None:
        return self.session.get(ResourceSource, source_id)

    def find_category(self, category_id: int) -> ResourceCategory | None:
        return self.session.get(ResourceCategory, category_id)

    def find_by_canonical_url(self, external_url: str) -> WellnessResource | None:
        """Deduplication basis for normalized canonical URLs."""
        return self.session.scalar(
            select(WellnessResource).where(WellnessResource.external_url == external_url)
        )

    def list_categories_for_resource(self, resource_id: int) -> list[int]:
        return list(
            self.session.scalars(
                select(WellnessResourceCategory.category_id).where(
                    WellnessResourceCategory.resource_id == resource_id
                )
            )
        )
