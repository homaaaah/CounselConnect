"""enrollment_verification router.

Student route (session-authenticated student identity, ADR-019):
- POST /enrollment-verifications/cor (upload PDF, multipart)

Reviewer routes (COUNSELOR role — the approval authority; no admin role):
- GET  /enrollment-verifications/pending        (queue with applicant details)
- GET  /enrollment-verifications/history        (permanent decision record)
- GET  /enrollment-verifications/{id}/cor       (in-app PDF preview)
- POST /enrollment-verifications/{id}/approve
- POST /enrollment-verifications/{id}/reject     (comment required)

Action-endpoint names follow NAMING_CONVENTIONS.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response

from app.modules.accounts.models import User
from app.modules.enrollment_verification.schemas import (
    ApproveRequest,
    PendingItemResponse,
    RejectRequest,
    StudentSummaryResponse,
    VerificationFileMeta,
    VerificationResponse,
)
from app.modules.enrollment_verification.service import (
    EnrollmentVerificationService,
    get_enrollment_verification_service,
)
from app.shared.dependencies import get_current_user, require_counselor, require_roles

router = APIRouter(prefix="/enrollment-verifications", tags=["enrollment_verification"])


@router.post(
    "/cor",
    response_model=VerificationResponse,
    status_code=201,
    summary="Student: upload current COR (registration form) PDF",
)
def upload_cor(
    file: UploadFile,
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
    student: User = Depends(require_roles("STUDENT")),
):
    content = file.file.read()
    verification = service.submit_cor(student.user_id, content, file.filename or "cor.pdf")
    return verification


@router.get(
    "/pending",
    response_model=list[PendingItemResponse],
    summary="Counselor: pending queue with applicant details",
    dependencies=[Depends(require_counselor)],
)
def list_pending(service: EnrollmentVerificationService = Depends(get_enrollment_verification_service)):
    items = []
    for verification, student, file_row in service.list_pending():
        items.append(
            PendingItemResponse(
                verification=VerificationResponse.model_validate(verification),
                student=StudentSummaryResponse.model_validate(
                    student, from_attributes=True
                ),
                file=VerificationFileMeta.model_validate(file_row),
            )
        )
    return items


@router.get(
    "/history",
    response_model=list[PendingItemResponse],
    summary="Counselor: permanent review record (all applications; optional status filter)",
    dependencies=[Depends(require_counselor)],
)
def list_history(
    status: str | None = None,
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    """Permanent record of every registration application and its decision.

    Decided rows keep decision_at, reviewer, comment, and valid_until.
    `file` is omitted (null) because COR bytes are purged after decisions
    per the privacy boundary.
    """
    items = []
    for verification, student in service.list_history(status):
        items.append(
            PendingItemResponse(
                verification=VerificationResponse.model_validate(verification),
                student=StudentSummaryResponse.model_validate(
                    student, from_attributes=True
                ),
                file=None,
            )
        )
    return items


@router.get(
    "/{verification_id}/cor",
    summary="Counselor: view the uploaded COR PDF",
)
def get_cor_pdf(
    verification_id: int,
    counselor: User = Depends(require_counselor),
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    """Serves the PDF for the counselor's in-app preview (session cookie)."""
    content = service.read_cor_pdf(verification_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="cor-{verification_id}.pdf"'},
    )


@router.post(
    "/{verification_id}/approve",
    response_model=VerificationResponse,
    summary="Counselor: approve the registration application",
)
def approve(
    verification_id: int,
    data: ApproveRequest | None = None,
    counselor: User = Depends(require_counselor),
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    months = data.valid_months if data is not None else 12
    verification, email_queued = service.approve(
        verification_id, reviewer_user_id=counselor.user_id, valid_months=months
    )
    verification.email_queued = email_queued
    return verification


@router.post(
    "/{verification_id}/reject",
    response_model=VerificationResponse,
    summary="Counselor: reject the registration application (comment required)",
)
def reject(
    verification_id: int,
    data: RejectRequest,
    counselor: User = Depends(require_counselor),
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    verification, email_queued = service.reject(
        verification_id, reviewer_user_id=counselor.user_id, reason=data.comment
    )
    verification.email_queued = email_queued
    return verification
