"""profile_change Pydantic contracts (ADR-032)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChangeRequestStatus = Literal["PENDING", "APPROVED", "REJECTED", "RETURNED"]
CorrectionField = Literal["first_name", "middle_name", "last_name", "year_level", "section"]


class CorrectionRegisteredValues(BaseModel):
    """Allowlisted comparison fields; never serialize the stored JSON directly."""

    first_name: str
    middle_name: str | None
    last_name: str
    year_level: int = Field(ge=1, le=10, strict=True)
    section: str


class StudentProfileChangeRequestResponse(BaseModel):
    """Own request and outcome, without reviewer IDs or private evidence metadata."""

    model_config = ConfigDict(from_attributes=True)

    change_request_id: int
    student_user_id: int
    cor_screening_id: int
    submission_version: int | None
    previous_change_request_id: int | None
    root_change_request_id: int | None
    status: ChangeRequestStatus
    requested_first_name: str
    requested_middle_name: str | None
    requested_last_name: str
    requested_year_level: int
    requested_section: str
    reviewed_at: datetime | None
    decision_reason: str | None
    created_at: datetime

    @field_validator("created_at", "reviewed_at")
    @classmethod
    def utc_timestamp(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class StudentProfileChangeRequestItem(BaseModel):
    # Informational owner action availability; POST independently rechecks.
    can_resubmit: bool = False
    change_request: StudentProfileChangeRequestResponse
    current_first_name: str
    current_middle_name: str | None
    current_last_name: str
    current_year_level: int | None
    current_section: str | None
    registered_values_at_submission: CorrectionRegisteredValues | None
    # Null is unknown legacy context; [] means a known comparison has no changes.
    changed_fields: list[CorrectionField] | None


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

    @field_validator("created_at", "reviewed_at")
    @classmethod
    def utc_timestamp(cls, value):
        return StudentProfileChangeRequestResponse.utc_timestamp(value)


class ReviewProfileChangeRequestResponse(ProfileChangeRequestResponse):
    """Review-list version links; legacy unknown versions remain null."""

    submission_version: int | None
    previous_change_request_id: int | None
    root_change_request_id: int | None


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

    change_request: ReviewProfileChangeRequestResponse
    student: ChangeRequestStudentSummary
    current_first_name: str
    current_middle_name: str | None
    current_last_name: str
    current_year_level: int | None
    current_section: str | None
    changed_fields: list[CorrectionField] | None = None


class RegistrationSnapshot(BaseModel):
    """Complete structured context only; all keys required, explicit nulls kept."""

    student_number: str | None
    first_name: str | None
    middle_name: str | None
    last_name: str | None
    campus_id: int | None = Field(gt=0, strict=True)
    program_id: int | None = Field(gt=0, strict=True)
    year_level: int | None = Field(ge=1, le=10, strict=True)
    section: str | None
    academic_period: str | None
    valid_until: date | None

    @field_validator("valid_until", mode="before")
    @classmethod
    def iso_date(cls, value):
        if value is None or type(value) is date:
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise ValueError("Invalid date")


class CorrectionHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    change_request_id: int
    submission_version: int | None
    status: ChangeRequestStatus
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    decision_reason: str | None

    @field_validator("created_at", "reviewed_at")
    @classmethod
    def utc_timestamp(cls, value):
        return StudentProfileChangeRequestResponse.utc_timestamp(value)


class CorrectionEvidenceStatus(BaseModel):
    availability: Literal["AVAILABLE", "UNAVAILABLE", "EXPIRED", "REPLACED", "CORRUPT", "RESOLVED", "LEGACY_UNKNOWN"]
    expires_at: datetime | None

    @field_validator("expires_at")
    @classmethod
    def utc_timestamp(cls, value):
        return StudentProfileChangeRequestResponse.utc_timestamp(value)


class ReviewProfileChangeRequestDetail(BaseModel):
    """Superadmin structured review context; private evidence access is separate."""

    change_request: ReviewProfileChangeRequestResponse
    student: ChangeRequestStudentSummary
    extracted_values: RegistrationSnapshot | None
    registered_values_at_submission: RegistrationSnapshot | None
    current_registered_values: RegistrationSnapshot
    proposed_changes: dict[CorrectionField, str | int | None]
    changed_fields: list[CorrectionField] | None
    history: list[CorrectionHistoryEntry]
    evidence: CorrectionEvidenceStatus
    # Resubmission is owner-only; reviewer responses never grant that action.
    can_resubmit: Literal[False] = False


class ApproveChangeRequestRequest(BaseModel):
    """Approve only the exact version displayed to the reviewer."""

    model_config = ConfigDict(extra="forbid")

    submission_version: int = Field(ge=1, strict=True)


class ReturnChangeRequestRequest(BaseModel):
    """Explicit version (null for legacy) and purpose-bound return reason."""

    model_config = ConfigDict(extra="forbid")

    submission_version: int | None = Field(ge=1, strict=True)
    reason: str = Field(max_length=500, description="Trimmed nonblank reason explaining what to fix")

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value):
        return value.strip() if isinstance(value, str) else value
