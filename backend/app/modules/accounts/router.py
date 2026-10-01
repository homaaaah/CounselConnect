"""accounts router — public endpoints for registration + reference data.

Counselor-only management endpoints arrive with ADR-P01 (auth context).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import EmailStr

from app.modules.accounts.schemas import (
    CampusResponse,
    ProgramResponse,
    RegistrationResultResponse,
    StudentProfileResponse,
    StudentRegistrationRequest,
    UserResponse,
)
from app.modules.accounts.service import AccountsService, get_accounts_service
from app.modules.cor_screening.schemas import (
    CorScreeningResponse,
    RegistrationWithCorResponse,
    StudentDirectoryItem,
)
from app.modules.cor_screening.service import (
    CorScreeningService,
    get_cor_screening_service,
)
from app.shared.dependencies import CurrentUser
from app.shared.pagination import ListEnvelope, paginate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post(
    "/register/student",
    response_model=RegistrationResultResponse,
    status_code=201,
    summary="Student self-registration (DFD 1.1; account starts PENDING_VERIFICATION)",
)
def register_student(
    data: StudentRegistrationRequest,
    service: AccountsService = Depends(get_accounts_service),
):
    user, profile = service.register_student(data)
    return RegistrationResultResponse(
        user=user,
        profile=profile,
        next_step="Upload your current COR for verification to activate the account.",
    )


@router.post(
    "/register/student-with-cor",
    response_model=RegistrationWithCorResponse,
    status_code=201,
    summary="Atomic registration: account + automated COR screening (ADR-029)",
)
def register_student_with_cor(
    response: Response,
    email: EmailStr = Form(...),
    password: str = Form(..., min_length=8, max_length=128),
    file: UploadFile = File(..., description="Current COR PDF (registration form)"),
    service: AccountsService = Depends(get_accounts_service),
):
    from app.config import get_settings

    # The one-time verification token is returned in this body: never cache it.
    response.headers["Cache-Control"] = "no-store"
    # Sync endpoint (threadpooled) because screening runs blocking OCR
    # subprocesses. Read only enough to validate the configured limit,
    # including one extra byte to detect an oversized upload.
    cor_content = file.file.read(get_settings().cor_max_mb * 1024 * 1024 + 1)
    user, screening, unmatched_campus, unmatched_program, verification_token = (
        service.register_student_with_cor(
            str(email),
            password,
            cor_content,
            file.filename or "cor.pdf",
        )
    )
    if screening.status == "AWAITING_CONFIRMATION":
        next_step = (
            "Your registration form passed screening. Confirm your details to "
            "activate your account."
        )
    else:
        next_step = (
            "Some details on your registration form could not be read. Upload a "
            "clearer COR to continue."
        )
    return RegistrationWithCorResponse(
        user=UserResponse.model_validate(user),
        screening=CorScreeningResponse.model_validate(screening),
        verification_token=verification_token,
        unmatched_campus_name=unmatched_campus,
        unmatched_program_name=unmatched_program,
        next_step=next_step,
    )


@router.get(
    "/campuses", response_model=ListEnvelope[CampusResponse], summary="Active campuses"
)
def list_campuses(service: AccountsService = Depends(get_accounts_service)):
    items = [CampusResponse.model_validate(c) for c in service.list_active_campuses()]
    return paginate(items, page=1, page_size=max(len(items), 1))


@router.get(
    "/programs", response_model=ListEnvelope[ProgramResponse], summary="Active programs"
)
def list_programs(service: AccountsService = Depends(get_accounts_service)):
    items = [ProgramResponse.model_validate(p) for p in service.list_active_programs()]
    return paginate(items, page=1, page_size=max(len(items), 1))


@router.get(
    "/guidance-staff", response_model=list[UserResponse]
)
def list_guidance_staff(
    actor: CurrentUser,
    service: AccountsService = Depends(get_accounts_service),
):
    return [UserResponse.model_validate(user) for user in service.list_active_guidance_staff(actor)]


@router.get(
    "/students",
    response_model=ListEnvelope[StudentDirectoryItem],
    summary="Counselor: read-only student directory with COR screening status",
)
def list_students(
    actor: CurrentUser,
    q: str | None = None,
    account_status: str | None = None,
    screening_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    rows = service.list_students(
        actor,
        q=q,
        account_status=account_status,
        screening_status=screening_status,
    )
    items = [
        StudentDirectoryItem(
            user=UserResponse.model_validate(user),
            profile=StudentProfileResponse.model_validate(profile) if profile is not None else None,
            screening=CorScreeningResponse.model_validate(screening) if screening is not None else None,
        )
        for user, profile, screening in rows
    ]
    return paginate(items, page=page, page_size=page_size)


@router.post(
    "/students/{user_id}/recover",
    response_model=StudentDirectoryItem,
    summary="Superadmin: recover a stuck Student account (ADR-030)",
)
def recover_student(
    user_id: int,
    actor: CurrentUser,
    service: CorScreeningService = Depends(get_cor_screening_service),
):
    user, profile, screening = service.recover_student(actor, user_id)
    return StudentDirectoryItem(
        user=UserResponse.model_validate(user),
        profile=StudentProfileResponse.model_validate(profile) if profile is not None else None,
        screening=CorScreeningResponse.model_validate(screening) if screening is not None else None,
    )
