"""appointments Pydantic contracts (docs/API_CONTRACT.md shapes)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DeliveryMode = Literal["ONLINE", "FACE_TO_FACE", "BOTH"]
AppointmentMode = Literal["ONLINE", "FACE_TO_FACE"]
AppointmentStatus = Literal["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "REJECTED", "NO_SHOW"]


class AvailabilitySlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slot_id: int
    counselor_user_id: int
    campus_id: int
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime
    status: Literal["AVAILABLE", "RESERVED"]


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: int
    student_user_id: int
    counselor_user_id: int
    availability_slot_id: int
    appointment_mode: AppointmentMode
    meeting_location: str | None
    conversation_id: int | None
    status: AppointmentStatus
    rejection_note: str | None
    created_at: datetime
    updated_at: datetime
