"""accounts Pydantic contracts (docs/API_CONTRACT.md shapes).

snake_case DTO fields; SCREAMING_SNAKE_CASE enum values (NAMING_CONVENTIONS.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RoleCode = Literal["STUDENT", "GUIDANCE_STAFF", "COUNSELOR"]
AccountStatus = Literal["PENDING_VERIFICATION", "ACTIVE", "VERIFICATION_EXPIRED"]


class StudentRegistrationRequest(BaseModel):
    """DFD 1.1 'Register Student Account' payload.

    Creates the pending account + academic profile; COR upload is a
    separate step (limits pending ADR-P05).
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
