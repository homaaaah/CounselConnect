"""audit Pydantic contracts (docs/API_CONTRACT.md shapes)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_event_id: int
    actor_user_id: int | None
    event_type: str
    target_type: str
    target_id: int | None
    outcome: str
    metadata_json: dict[str, Any] | None
    occurred_at: datetime
