"""messaging router (thin HTTP transport).

Nested resource per NAMING_CONVENTIONS.md:
/conversations/{conversation_id}/messages
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.messaging.service import MessagingService, get_messaging_service

router = APIRouter(prefix="/conversations", tags=["messaging"])
