"""Registration corrections: own Student status reads and Superadmin review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.config import get_settings

from app.modules.profile_change.schemas import (
    ProfileChangeRequestItem,
    ChangeRequestStatus,
    StudentProfileChangeRequestItem,
    ReviewProfileChangeRequestDetail,
    ApproveChangeRequestRequest,
    ReturnChangeRequestRequest,
)
from app.modules.profile_change.service import (
    ProfileChangeService,
    get_profile_change_service,
)
from app.shared.dependencies import CurrentUser
from app.shared.pagination import ListEnvelope

router = APIRouter(prefix="/profile-change-requests", tags=["profile_change"])


@router.post(
    "/{change_request_id}/resubmit", status_code=201, response_model=StudentProfileChangeRequestItem,
    summary="Student: resubmit a returned correction with a fresh current COR",
    description="Session and CSRF required. Exactly one of each multipart field; no extra parts. "
                "Use literal null only for a legacy unknown submission version.",
)
async def resubmit_change_request(
    change_request_id: int, request: Request, response: Response, actor: CurrentUser,
    file: UploadFile = File(..., description="Fresh current COR PDF"),
    submission_version: str = Form(..., pattern=r"^(null|[1-9][0-9]*)$", max_length=20),
    proposed_changes: str = Form(..., max_length=4096,
        description="JSON object limited to first_name, middle_name, last_name, year_level and section"),
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        service._require_student_read(actor)
        form = await request.form()
        fields = {"file", "submission_version", "proposed_changes"}
        if set(form) != fields or any(len(form.getlist(field)) != 1 for field in fields):
            raise AppError(code="VALIDATION_ERROR", message="Supply exactly one of each supported multipart field.", status_code=422)
        limit = get_settings().cor_max_mb * 1024 * 1024
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise AppError(code="COR_TOO_LARGE", message="The COR exceeds the upload size limit.", status_code=422)
        version = None if submission_version == "null" else int(submission_version)

        def submit():
            row = service.resubmit(actor, change_request_id, submission_version=version,
                proposed_changes=proposed_changes, content=content, filename=file.filename or "cor.pdf")
            return service.get_student_request(actor, row.change_request_id)

        return await run_in_threadpool(submit)
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(exc.to_payload()),
                            headers={"Cache-Control": "no-store"})


@router.get(
    "",
    response_model=ListEnvelope[ProfileChangeRequestItem] | ListEnvelope[StudentProfileChangeRequestItem],
    summary="List correction requests (own Student status or Superadmin queue)",
)
def list_change_requests(
    response: Response,
    actor: CurrentUser,
    status: ChangeRequestStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    root_change_request_id: int | None = Query(default=None, gt=0, le=18446744073709551615),
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    response.headers["Cache-Control"] = "no-store"
    if actor.role_code == "STUDENT":
        return service.list_student_requests(actor, status=status, page=page, page_size=page_size,
                                             root_change_request_id=root_change_request_id)
    return service.list_requests(actor, status=status, page=page, page_size=page_size,
                                 root_change_request_id=root_change_request_id)


@router.get(
    "/{change_request_id}", response_model=StudentProfileChangeRequestItem | ReviewProfileChangeRequestDetail,
    summary="Read own Student status or Superadmin correction review detail",
)
def get_student_change_request(
    change_request_id: int,
    response: Response,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    response.headers["Cache-Control"] = "no-store"
    if actor.role_code == "SUPERADMIN":
        return service.get_review_request(actor, change_request_id)
    return service.get_student_request(actor, change_request_id)


@router.post(
    "/{change_request_id}/approve",
    response_model=ReviewProfileChangeRequestDetail,
    summary="Superadmin: approve a profile edit request (ADR-032)",
)
def approve_change_request(
    change_request_id: int,
    data: ApproveChangeRequestRequest,
    response: Response,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    response.headers["Cache-Control"] = "no-store"
    service.approve(actor, change_request_id, submission_version=data.submission_version)
    return service.get_review_request(actor, change_request_id)


@router.post(
    "/{change_request_id}/return", response_model=ReviewProfileChangeRequestDetail,
    summary="Superadmin: return the whole correction version with a reason",
)
def return_change_request(
    change_request_id: int,
    data: ReturnChangeRequestRequest,
    response: Response,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    response.headers["Cache-Control"] = "no-store"
    service.return_request(actor, change_request_id, data.reason, submission_version=data.submission_version)
    return service.get_review_request(actor, change_request_id)


@router.post(
    "/{change_request_id}/reject",
    response_model=ReviewProfileChangeRequestDetail,
    deprecated=True,
    summary="Superadmin: compatibility alias for version-bound correction return",
)
def reject_change_request(
    change_request_id: int,
    data: ReturnChangeRequestRequest,
    response: Response,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    response.headers["Cache-Control"] = "no-store"
    service.reject(actor, change_request_id, data.reason, submission_version=data.submission_version)
    return service.get_review_request(actor, change_request_id)


@router.get(
    "/{change_request_id}/cor", response_class=Response,
    summary="Superadmin: retrieve the exact pending correction COR privately",
    responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
               403: {"description": "Reviewer access denied"},
               404: {"description": "Change request not found"},
               409: {"description": "Exact evidence unavailable"}},
)
def get_change_request_cor(
    change_request_id: int,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    # Keep service errors in the standard envelope and prevent caching of
    # private evidence outcomes as well as successful PDF responses.
    try:
        content = service.read_review_cor(actor, change_request_id)
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(exc.to_payload()),
                            headers={"Cache-Control": "no-store"})
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": 'inline; filename="registration-correction-cor.pdf"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })
