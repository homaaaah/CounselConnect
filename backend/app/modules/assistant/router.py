"""assistant router (thin HTTP transport)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.assistant.service import AssistantService, get_assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])
