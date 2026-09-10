"""Appointment scheduling contracts; timestamps serialize in UTC."""

from datetime import date, datetime, time, timezone
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

DeliveryMode = Literal["ONLINE", "FACE_TO_FACE", "BOTH"]
AppointmentMode = Literal["ONLINE", "FACE_TO_FACE"]
AppointmentStatus = Literal[
    "PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "REJECTED", "NO_SHOW"
]


class AvailabilitySlotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campus_id: int = Field(gt=0)
    delivery_mode: DeliveryMode
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    slot_duration_minutes: int = Field(
        gt=0, description="Counselor-selected duration; no policy default."
    )

    @model_validator(mode="after")
    def validate_range(self):
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        seconds = (self.ends_at - self.starts_at).total_seconds()
        duration = self.slot_duration_minutes * 60
        if seconds <= 0 or seconds % duration or seconds / duration > 200:
            raise ValueError("Range must contain 1 to 200 whole slots.")
        return self


class AppointmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    availability_slot_id: int = Field(gt=0)
    appointment_mode: AppointmentMode


class AppointmentRescheduleRequest(AppointmentCreateRequest):
    pass


class AppointmentRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rejection_note: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
        ]
        | None
    ) = None


class GuidanceOfficeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guidance_office_location: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]


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


class AvailabilitySlotResponse(UTCResponse):
    slot_id: int
    counselor_user_id: int
    counselor_name: str
    campus_id: int
    campus_name: str
    guidance_office_location: str | None
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime
    status: Literal["AVAILABLE", "RESERVED"]


class AppointmentResponse(UTCResponse):
    appointment_id: int
    student_user_id: int
    student_name: str
    counselor_user_id: int
    counselor_name: str
    availability_slot_id: int
    campus_id: int
    campus_name: str
    starts_at: datetime
    ends_at: datetime
    appointment_mode: AppointmentMode
    meeting_location: str | None
    conversation_id: int | None
    status: AppointmentStatus
    rejection_note: str | None
    created_at: datetime
    updated_at: datetime


class CalendarBlockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocked_date: date
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


class CalendarDayResponse(BaseModel):
    calendar_date: date
    is_weekday: bool
    is_blocked: bool
    available_times: list[str]


class CalendarResponse(BaseModel):
    timezone: str
    business_hours: str
    days: list[CalendarDayResponse]


class WeeklyScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campus_id: int = Field(gt=0)
    day_of_week: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(ge=15, le=240)
    delivery_mode: DeliveryMode

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_time <= self.start_time:
            raise ValueError("The end time must be after the start time.")
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        if (end - start) % self.slot_duration_minutes:
            raise ValueError("The selected time range must contain whole appointment slots.")
        return self


class WeeklyScheduleResponse(UTCResponse):
    weekly_schedule_id: int
    counselor_user_id: int
    campus_id: int
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    delivery_mode: DeliveryMode
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AvailabilityBlockCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    is_all_day: bool = False
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None

    @model_validator(mode="after")
    def validate_range(self):
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        if self.ends_at <= self.starts_at:
            raise ValueError("The block end must be after its start.")
        return self


class AvailabilityBlockResponse(UTCResponse):
    availability_block_id: int
    counselor_user_id: int
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool
    reason: str | None
    created_at: datetime
    updated_at: datetime
