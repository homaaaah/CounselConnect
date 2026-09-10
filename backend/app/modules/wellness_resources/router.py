"""wellness_resources router (thin HTTP transport).

Action endpoint per NAMING_CONVENTIONS.md:
POST /wellness-resources/{resource_id}/publish
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.wellness_resources.service import (
    WellnessResourcesService,
    get_wellness_resources_service,
)

router = APIRouter(prefix="/wellness-resources", tags=["wellness_resources"])
