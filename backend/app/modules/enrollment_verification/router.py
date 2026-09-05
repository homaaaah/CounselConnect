"""enrollment_verification router.

Student route: POST /enrollment-verifications/cor (upload PDF, multipart).
Reviewer (COUNSELOR) routes — until ADR-P01 lands, protected by the
temporary dev admin key (X-Admin-Key) instead of real auth:
- GET  /enrollment-verifications/pending        (queue with applicant details)
- GET  /enrollment-verifications/{id}/detail     (full applicant detail)
- GET  /enrollment-verifications/{id}/cor       (in-app PDF preview)
- POST /enrollment-verifications/{id}/approve
- POST /enrollment-verifications/{id}/reject     (comment required)

Action-endpoint names follow NAMING_CONVENTIONS.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import get_settings
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

router = APIRouter(prefix="/enrollment-verifications", tags=["enrollment_verification"])

# Temporary dev reviewer identity until ADR-P01 provides real auth.
DEV_REVIEWER_USER_ID = 1


def _require_reviewer_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Dev-only guard: reviewer endpoints need the configured key.

    # TODO: Replace with the real COUNSELOR authorization dependency
    # once ADR-P01 approves the auth mechanism.
    """
    key = get_settings().dev_admin_key
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Reviewer access is disabled until COUNSELCONNECT_DEV_ADMIN_KEY is configured.",
        )
    if x_admin_key != key:
        raise HTTPException(status_code=401, detail="Invalid reviewer key.")


@router.post(
    "/cor",
    response_model=VerificationResponse,
    status_code=201,
    summary="Student: upload current COR (registration form) PDF",
)
def upload_cor(
    file: UploadFile,
    student_user_id: int,  # TODO: from the authenticated student (ADR-P01)
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    content = file.file.read()
    verification = service.submit_cor(student_user_id, content, file.filename or "cor.pdf")
    return verification


@router.get(
    "/pending",
    response_model=list[PendingItemResponse],
    summary="Reviewer: pending queue with applicant details",
    dependencies=[Depends(_require_reviewer_key)],
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
    summary="Reviewer: permanent review record (all applications; optional status filter)",
    dependencies=[Depends(_require_reviewer_key)],
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
    summary="Reviewer: view the uploaded COR PDF",
)
def get_cor_pdf(
    verification_id: int,
    admin_key: str = Header(default=None, alias="X-Admin-Key"),
    key: str | None = None,  # query fallback: browsers cannot set headers in new tabs
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    """Serves the PDF for the reviewer's in-app preview.

    Accepts the reviewer key via the X-Admin-Key header OR a `?key=`
    query parameter — a plain browser tab (the 'View PDF' link) cannot
    set custom headers, so the link carries the key in the query string.
    """
    from fastapi import HTTPException

    expected = get_settings().dev_admin_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Reviewer access is disabled until COUNSELCONNECT_DEV_ADMIN_KEY is configured.",
        )
    if admin_key != expected and key != expected:
        raise HTTPException(status_code=401, detail="Invalid reviewer key.")
    content = service.read_cor_pdf(verification_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="cor-{verification_id}.pdf"'},
    )


@router.post(
    "/{verification_id}/approve",
    response_model=VerificationResponse,
    summary="Reviewer: approve the registration application",
    dependencies=[Depends(_require_reviewer_key)],
)
def approve(
    verification_id: int,
    data: ApproveRequest | None = None,
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    months = data.valid_months if data is not None else 12
    verification, email_queued = service.approve(
        verification_id, reviewer_user_id=DEV_REVIEWER_USER_ID, valid_months=months
    )
    verification.email_queued = email_queued
    return verification


@router.post(
    "/{verification_id}/reject",
    response_model=VerificationResponse,
    summary="Reviewer: reject the registration application (comment required)",
    dependencies=[Depends(_require_reviewer_key)],
)
def reject(
    verification_id: int,
    data: RejectRequest,
    service: EnrollmentVerificationService = Depends(get_enrollment_verification_service),
):
    verification, email_queued = service.reject(
        verification_id, reviewer_user_id=DEV_REVIEWER_USER_ID, reason=data.comment
    )
    verification.email_queued = email_queued
    return verification
