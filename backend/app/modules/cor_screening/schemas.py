"""cor_screening Pydantic contracts (snake_case DTOs, SCREAMING_SNAKE enums)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.accounts.schemas import StudentProfileResponse, UserResponse

ScreeningStatus = Literal[
    "PROCESSING", "AWAITING_CONFIRMATION", "PASSED", "NEEDS_RESUBMISSION", "FAILED"
]
BarcodeStatus = Literal[
    "NOT_PROCESSED", "NOT_FOUND", "UNREADABLE", "INVALID_FORMAT", "DECODED", "MISMATCH"
]


class CorScreeningResponse(BaseModel):
    """Screening result plus the extracted (unconfirmed) academic fields."""

    model_config = ConfigDict(from_attributes=True)

    cor_screening_id: int
    student_user_id: int
    status: ScreeningStatus
    format_template_version: str
    format_match_score: float | None
    extraction_confidence: float | None
    barcode_status: BarcodeStatus
    barcode_symbology: str | None
    failure_reason_code: str | None
    extracted_student_number: str | None
    extracted_first_name: str | None
    extracted_middle_name: str | None
    extracted_last_name: str | None
    extracted_campus_id: int | None
    extracted_program_id: int | None
    extracted_year_level: int | None
    extracted_section: str | None
    extracted_academic_period: str | None
    extracted_valid_until: date | None
    valid_until: date | None
    submitted_at: datetime
    processed_at: datetime | None
    confirmed_at: datetime | None


class RegistrationWithCorResponse(BaseModel):
    """Result of the atomic COR registration (account is PENDING_VERIFICATION)."""

    user: UserResponse
    screening: CorScreeningResponse
    unmatched_campus_name: str | None = None
    unmatched_program_name: str | None = None
    next_step: str


class ConfirmScreeningRequest(BaseModel):
    """Student-confirmed academic fields (COR is the source of truth)."""

    student_number: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    campus_id: int = Field(gt=0)
    program_id: int = Field(gt=0)
    year_level: int = Field(ge=1, le=10)
    section: str = Field(min_length=1, max_length=50)
    academic_period: str | None = Field(default=None, max_length=100)


class ConfirmScreeningResponse(BaseModel):
    screening: CorScreeningResponse
    user: UserResponse
    profile: StudentProfileResponse


class ResubmitResponse(BaseModel):
    screening: CorScreeningResponse


class CounselorScreeningItem(BaseModel):
    """Read-only screening record for Counselor recovery/audit views."""

    screening: CorScreeningResponse
    student: "ScreeningStudentSummary"


class ScreeningStudentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    account_status: str
    student_number: str | None = None


class StudentDirectoryItem(BaseModel):
    """One Student row in the Counselor directory (profile + latest screening)."""

    user: UserResponse
    profile: StudentProfileResponse | None = None
    screening: CorScreeningResponse | None = None
