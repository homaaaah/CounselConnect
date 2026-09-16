"""messaging Pydantic contracts (docs/API_CONTRACT.md shapes).

Nested resource per NAMING_CONVENTIONS.md:
/conversations/{conversation_id}/messages
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator
from typing import Annotated

ConversationType = Literal["GENERAL", "APPOINTMENT", "SOS"]


class UTCResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def serialize_database_datetimes_as_utc(cls, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return value


class ConversationResponse(UTCResponse):

    conversation_id: int
    student_user_id: int
    counselor_user_id: int | None
    appointment_id: int | None
    conversation_type: ConversationType
    status: Literal["OPEN", "CLOSED"]
    started_at: datetime
    closed_at: datetime | None
    messages_purged_at: datetime | None
    student_joined_at: datetime | None
    counselor_joined_at: datetime | None
    closure_reason: str | None
    last_sequence_number: int


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    client_message_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class MessageResponse(UTCResponse):

    message_id: int
    conversation_id: int
    sender_user_id: int
    client_message_id: str | None
    sequence_number: int
    body: str
    sent_at: datetime


class MessageHistoryResponse(BaseModel):
    items: list[MessageResponse]
    next_before_sequence: int | None
    next_after_sequence: int | None
    has_more: bool
    sequence_watermark: int
