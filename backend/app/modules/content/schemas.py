"""content Pydantic contracts (docs/API_CONTRACT.md shapes)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ContentType = Literal["CMS_BLOCK", "FAQ", "ANNOUNCEMENT"]


class ContentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_id: int
    content_type: ContentType
    content_key: str | None
    title: str | None
    body: str
    is_published: bool
    created_by_user_id: int | None
    updated_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class EmergencyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_id: int
    name: str
    contact_number: str
    description: str | None
    is_active: bool
    display_order: int
