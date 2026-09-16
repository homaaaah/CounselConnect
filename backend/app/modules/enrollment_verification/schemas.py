"""enrollment_verification Pydantic contracts (docs/API_CONTRACT.md shapes)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VerificationStatus = Literal["PENDING", "APPROVED", "NEEDS_RESUBMISSION", "REJECTED", "EXPIRED"]


class VerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_id: int
    student_user_id: int
    status: VerificationStatus
    submitted_at: datetime
    assigned_guidance_staff_user_id: int | None
    decision_at: datetime | None
    reviewed_by_user_id: int | None
    reason_code: str | None
    reviewer_note: str | None
    valid_until: date | None
    # Set after Gmail accepts the message, SMTP is absent, or delivery could
    # not be submitted. SMTP acceptance does not guarantee inbox placement.
    email_status: Literal["SENT", "NOT_CONFIGURED", "FAILED"] | None = None


class StudentSummaryResponse(BaseModel):
    """Applicant details shown to the reviewer (DFD 1.3 review screen)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    first_name: str
    middle_name: str | None
    last_name: str
    student_number: str | None = None
    campus_id: int | None = None
    program_id: int | None = None
    year_level: int | None = None
    section: str | None = None


class PendingItemResponse(BaseModel):
    """One queue/history entry: verification + applicant (+ COR metadata when pending)."""

    verification: VerificationResponse
    student: StudentSummaryResponse
    file: "VerificationFileMeta | None" = None


class VerificationFileMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: int
    verification_id: int
    mime_type: str
    size_bytes: int
    expires_at: datetime
    cleanup_state: Literal["PENDING", "FAILED"]


class RejectRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=500)


class ApproveRequest(BaseModel):
    valid_months: int = Field(default=12, ge=1, le=24)


class VerificationAssignmentRequest(BaseModel):
    guidance_staff_user_id: int = Field(gt=0)
