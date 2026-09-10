"""messaging Pydantic contracts (docs/API_CONTRACT.md shapes).

Nested resource per NAMING_CONVENTIONS.md:
/conversations/{conversation_id}/messages
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ConversationType = Literal["GENERAL", "APPOINTMENT", "SOS"]


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: int
    student_user_id: int
    counselor_user_id: int | None
    conversation_type: ConversationType
    status: Literal["OPEN", "CLOSED"]
    started_at: datetime
    closed_at: datetime | None
    messages_purged_at: datetime | None


class MessageCreateRequest(BaseModel):
    body: str
    client_message_id: str | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: int
    conversation_id: int
    sender_user_id: int
    client_message_id: str | None
    body: str
    sent_at: datetime
