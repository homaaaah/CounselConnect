"""profile_change Pydantic contracts (ADR-032)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChangeRequestStatus = Literal["PENDING", "APPROVED", "REJECTED"]


class ProfileChangeRequestResponse(BaseModel):
    """A Student's requested profile edit and its review state."""

    model_config = ConfigDict(from_attributes=True)

    change_request_id: int
    student_user_id: int
    cor_screening_id: int
    status: ChangeRequestStatus
    requested_first_name: str
    requested_middle_name: str | None
    requested_last_name: str
    requested_year_level: int
    requested_section: str
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    decision_reason: str | None
    created_at: datetime


class ChangeRequestStudentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    account_status: str


class ProfileChangeRequestItem(BaseModel):
    """Queue row: the request plus the Student's current values for the diff."""

    change_request: ProfileChangeRequestResponse
    student: ChangeRequestStudentSummary
    current_first_name: str
    current_middle_name: str | None
    current_last_name: str
    current_year_level: int | None
    current_section: str | None


class RejectChangeRequestRequest(BaseModel):
    """A rejection must record the reviewer's reason (ADR-024 precedent)."""

    reason: str = Field(min_length=1, max_length=500)
