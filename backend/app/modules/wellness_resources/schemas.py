"""wellness_resources Pydantic contracts (docs/API_CONTRACT.md shapes).

Action endpoint per NAMING_CONVENTIONS.md:
POST /wellness-resources/{resource_id}/publish
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ResourceType = Literal["EXTERNAL_LINK", "INTERNAL_ARTICLE", "INTERNAL_FILE"]
ResourceStatus = Literal["PENDING", "PUBLISHED", "REJECTED", "DISABLED"]


class WellnessResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resource_id: int
    resource_type: ResourceType
    source_id: int | None
    created_by_user_id: int | None
    title: str
    summary: str | None
    external_url: str | None
    status: ResourceStatus
    discovered_at: datetime | None
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResourceCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str
    slug: str
    is_active: bool
