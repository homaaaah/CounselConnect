"""cor_screening router.

Student (ADR-029 automated flow; session or X-COR-Token on the POSTs):
- GET  /cor-screenings/me             (latest screening for the signed-in Student)
- POST /cor-screenings/confirm        (confirm extracted fields -> activate account)
- POST /cor-screenings/request-edit   (request name/year/section edits; Superadmin approves)
- POST /cor-screenings/reject-account (cancel registration; deletes the account)
- POST /cor-screenings/reject         (deprecated for the UI; kept for compatibility)
- POST /cor-screenings/resubmit       (replace a failed/again-needed COR)

Counselor read-only recovery/audit view:
- GET  /cor-screenings           (list screenings; COUNSELOR only)

Registration entry (account + first screening) lives at
POST /accounts/register/student-with-cor in the accounts router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.modules.accounts.models import User
from app.modules.accounts.schemas import StudentProfileResponse, UserResponse
from app.modules.cor_screening.schemas import (
    ConfirmScreeningRequest,
    ConfirmScreeningResponse,
    CorScreeningResponse,
    CounselorScreeningItem,
    RequestEditRequest,
    RequestEditResponse,
    ResubmitResponse,
    ScreeningStudentSummary,
)
from app.modules.cor_screening.service import (
    CorScreeningService,
    get_cor_screening_service,
)
from app.modules.profile_change.schemas import ProfileChangeRequestResponse
from app.shared.dependencies import (
    CurrentUser,
    ScreeningActor,
    get_screening_actor,
    require_roles,
)
from app.shared.pagination import ListEnvelope, paginate

router = APIRouter(prefix="/cor-screenings", tags=["cor_screening"])


@router.get(
    "/me",
    response_model=CorScreeningResponse | None,
    summary="Student: latest COR screening result",
)
def get_my_screening(
    actor: User = Depends(require_roles("STUDENT")),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    return service.latest_for_student(actor)


@router.post(
    "/confirm",
    response_model=ConfirmScreeningResponse,
    summary="Student: confirm extracted COR fields and activate the account",
)
def confirm_screening(
    data: ConfirmScreeningRequest,
    actor: ScreeningActor = Depends(get_screening_actor),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    if actor.screening is not None:
        screening, user, profile = service.confirm_resolved(actor.user, actor.screening, data)
    else:
        screening, user, profile = service.confirm(actor.user, data)
    return ConfirmScreeningResponse(
        screening=CorScreeningResponse.model_validate(screening),
        user=UserResponse.model_validate(user),
        profile=StudentProfileResponse.model_validate(profile),
    )


@router.post(
    "/request-edit",
    response_model=RequestEditResponse,
    summary="Student: request edits during verification (Superadmin approves; ADR-032)",
)
def request_edit_screening(
    data: RequestEditRequest,
    actor: ScreeningActor = Depends(get_screening_actor),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    if actor.screening is not None:
        screening, user, profile, change_request = service.request_edit_resolved(
            actor.user, actor.screening, data
        )
    else:
        screening, user, profile, change_request = service.request_edit(actor.user, data)
    return RequestEditResponse(
        screening=CorScreeningResponse.model_validate(screening),
        user=UserResponse.model_validate(user),
        profile=StudentProfileResponse.model_validate(profile),
        change_request=(
            ProfileChangeRequestResponse.model_validate(change_request)
            if change_request is not None
            else None
        ),
    )


@router.post(
    "/reject",
    response_model=ResubmitResponse,
    summary="Student: reject the extracted details and re-upload the COR",
)
def reject_screening(
    actor: ScreeningActor = Depends(get_screening_actor),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    if actor.screening is not None:
        screening = service.reject_resolved(actor.user, actor.screening)
    else:
        screening = service.reject(actor.user)
    return ResubmitResponse(screening=CorScreeningResponse.model_validate(screening))


@router.post(
    "/reject-account",
    status_code=204,
    summary="Student: cancel registration and delete the account (ADR-033)",
)
def reject_account(
    actor: ScreeningActor = Depends(get_screening_actor),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    service.reject_account(actor.user)
    return Response(status_code=204)


@router.post(
    "/resubmit",
    response_model=ResubmitResponse,
    status_code=201,
    summary="Student: re-upload a COR after a failed screening",
)
def resubmit_cor(
    response: Response,
    actor: ScreeningActor = Depends(get_screening_actor),
    file: UploadFile = File(..., description="Current COR PDF (registration form)"),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    from app.config import get_settings

    # The rotated token is returned in this body: never cache it.
    response.headers["Cache-Control"] = "no-store"
    content = file.file.read(get_settings().cor_max_mb * 1024 * 1024 + 1)
    if actor.screening is not None:
        screening, token = service.resubmit_resolved(
            actor.user, actor.screening, content, file.filename or "cor.pdf"
        )
    else:
        screening, token = service.resubmit(actor.user, content, file.filename or "cor.pdf")
    return ResubmitResponse(
        screening=CorScreeningResponse.model_validate(screening),
        verification_token=token,
    )


@router.get(
    "",
    response_model=ListEnvelope[CounselorScreeningItem],
    summary="Counselor: read-only screening records",
)
def list_screenings(
    actor: CurrentUser,
    status: str | None = None,
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    items = []
    for screening, student, profile in service.list_for_counselor(actor, status):
        items.append(
            CounselorScreeningItem(
                screening=CorScreeningResponse.model_validate(screening),
                student=ScreeningStudentSummary(
                    user_id=student.user_id,
                    email=student.email,
                    first_name=student.first_name,
                    middle_name=student.middle_name,
                    last_name=student.last_name,
                    account_status=student.account_status,
                    student_number=profile.student_number if profile is not None else None,
                ),
            )
        )
    return paginate(items, page=1, page_size=max(len(items), 1))
