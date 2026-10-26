"""accounts Pydantic contracts (docs/API_CONTRACT.md shapes).

snake_case DTO fields; SCREAMING_SNAKE_CASE enum values (NAMING_CONVENTIONS.md).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

RoleCode = Literal["STUDENT", "GUIDANCE_STAFF", "COUNSELOR", "SUPERADMIN"]
AccountStatus = Literal["PENDING_VERIFICATION", "ACTIVE", "VERIFICATION_EXPIRED"]


class StudentRegistrationRequest(BaseModel):
    """DFD 1.1 'Register Student Account' payload.

    Creates the pending account + academic profile; COR upload is a
    separate step (limits ratified by ADR-024).
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    student_number: str = Field(min_length=1, max_length=50)
    campus_id: int = Field(gt=0)
    program_id: int = Field(gt=0)
    year_level: int = Field(ge=1, le=10)
    section: str = Field(min_length=1, max_length=50)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: EmailStr
    role_code: RoleCode
    account_status: AccountStatus
    first_name: str
    middle_name: str | None
    last_name: str
    created_at: datetime
    updated_at: datetime


class ManagedUserSummary(UserResponse):
    is_deactivated: bool
    student_number: str | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ManagedStudentProfile(BaseModel):
    student_number: str
    campus_id: int | None
    program_id: int | None
    year_level: int | None
    section: str | None


class ManagedUserDetail(ManagedUserSummary):
    profile: ManagedStudentProfile | None = None
    campus_name: str | None = None
    program_name: str | None = None
    valid_until: date | None = None


class UserStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CounselorAccountFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    first_name: str = Field(strict=True, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, strict=True, max_length=100)
    last_name: str = Field(strict=True, min_length=1, max_length=100)

    @field_validator("first_name", "middle_name", "last_name", mode="before")
    @classmethod
    def normalize_name(cls, value, info):
        if isinstance(value, str):
            value = " ".join(value.split())
            return None if info.field_name == "middle_name" and not value else value
        return value

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value):
        return value.strip() if isinstance(value, str) else value


class CounselorAccountCreateRequest(CounselorAccountFields):
    password: SecretStr = Field(min_length=8, max_length=128)


class CounselorAccountUpdateRequest(CounselorAccountFields):
    middle_name: str | None = Field(strict=True, max_length=100)
    expected_updated_at: AwareDatetime

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def require_timestamp(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("A timezone-aware timestamp is required.")
        return value


class CampusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campus_id: int
    campus_name: str
    guidance_office_location: str | None
    is_active: bool


class ProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    program_id: int
    department_id: int
    program_code: str
    program_name: str
    is_active: bool


class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    student_number: str
    campus_id: int
    program_id: int
    year_level: int
    section: str


class RegistrationResultResponse(BaseModel):
    """Result of student self-registration (always PENDING_VERIFICATION)."""

    user: UserResponse
    profile: StudentProfileResponse
    next_step: str
