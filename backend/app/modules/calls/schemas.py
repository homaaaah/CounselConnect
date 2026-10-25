"""Appointment call contracts (ADR-034).

Only authorized participants inside the appointment window receive ICE server
details. No SDP, ICE candidates, media, or call history are persisted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

ParticipantRole = Literal["STUDENT", "COUNSELOR"]


class CallIceServer(BaseModel):
    urls: list[str]
    username: str | None = None
    credential: str | None = None


class UTCResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc_datetimes(cls, value):
        if isinstance(value, datetime):
            return (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            )
        return value


class CallConfigResponse(UTCResponse):
    appointment_id: int
    role: ParticipantRole
    peer_role: ParticipantRole
    can_call: bool
    starts_at: datetime
    ends_at: datetime
    safety_deadline_at: datetime
    server_time: datetime
    ice_servers: list[CallIceServer]
