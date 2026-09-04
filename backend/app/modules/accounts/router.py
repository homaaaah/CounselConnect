"""accounts router — public endpoints for registration + reference data.

Counselor-only management endpoints arrive with ADR-P01 (auth context).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import EmailStr

from app.core.exceptions import AppError
from app.modules.accounts.schemas import (
    CampusResponse,
    ProgramResponse,
    RegistrationResultResponse,
    StudentRegistrationRequest,
)
from app.modules.accounts.service import AccountsService, get_accounts_service
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
    response_model=RegistrationResultResponse,
    status_code=201,
    summary="Atomic registration: account + COR PDF in ONE submission (DFD 1.1 + 1.2)",
)
async def register_student_with_cor(
    first_name: str = Form(...),
    middle_name: str | None = Form(default=None),
    last_name: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(..., min_length=8, max_length=128),
    student_number: str = Form(...),
    campus_id: int = Form(..., gt=0),
    program_id: int = Form(..., gt=0),
    year_level: int = Form(..., ge=1, le=10),
    section: str = Form(...),
    file: UploadFile = File(..., description="Current COR PDF (registration form)"),
    service: AccountsService = Depends(get_accounts_service),
):
    cor_content = await file.read()
    user, profile, verification = service.register_student_with_cor(
        SimpleNamespace(
            email=email,
            password=password,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            student_number=student_number,
            campus_id=campus_id,
            program_id=program_id,
            year_level=year_level,
            section=section,
        ),
        cor_content,
        file.filename or "cor.pdf",
    )
    return RegistrationResultResponse(
        user=user,
        profile=profile,
        next_step=(
            "Registration and registration form (COR) submitted together. "
            "The Guidance Counselor will review your application — you will "
            "receive an email once decided."
        ),
    )


@router.get("/campuses", response_model=ListEnvelope[CampusResponse],
            summary="Active campuses")
def list_campuses(service: AccountsService = Depends(get_accounts_service)):
    items = [CampusResponse.model_validate(c) for c in service.list_active_campuses()]
    return paginate(items, page=1, page_size=max(len(items), 1))


@router.get(
    "/lookup",
    summary="Look up the user id for an email (supports the post-registration COR upload step)",
)
def lookup_user(email: str, service: AccountsService = Depends(get_accounts_service)):
    """Dev-scaffold endpoint: returns only {user_id} or 404.

    # TODO: Remove when the COR upload attaches to the authenticated
    # student session after ADR-P01.
    """
    user = service.repository.find_user_by_email(email)
    if user is None:
        raise AppError(code="USER_NOT_FOUND", message="No account with that email.", status_code=404)
    return {"user_id": user.user_id}


@router.get("/programs", response_model=ListEnvelope[ProgramResponse],
            summary="Active programs")
def list_programs(service: AccountsService = Depends(get_accounts_service)):
    items = [ProgramResponse.model_validate(p) for p in service.list_active_programs()]
    return paginate(items, page=1, page_size=max(len(items), 1))
