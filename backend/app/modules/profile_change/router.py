"""profile_change router: Superadmin review of Student profile-edit requests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.profile_change.schemas import (
    ProfileChangeRequestItem,
    ProfileChangeRequestResponse,
    RejectChangeRequestRequest,
)
from app.modules.profile_change.service import (
    ProfileChangeService,
    get_profile_change_service,
)
from app.shared.dependencies import CurrentUser
from app.shared.pagination import ListEnvelope, paginate

router = APIRouter(prefix="/profile-change-requests", tags=["profile_change"])


@router.get(
    "",
    response_model=ListEnvelope[ProfileChangeRequestItem],
    summary="Superadmin: list profile edit requests (ADR-032)",
)
def list_change_requests(
    actor: CurrentUser,
    status: str | None = Query(default="PENDING"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    items = service.list_requests(actor, status=status)
    return paginate(items, page=page, page_size=page_size)


@router.post(
    "/{change_request_id}/approve",
    response_model=ProfileChangeRequestResponse,
    summary="Superadmin: approve a profile edit request (ADR-032)",
)
def approve_change_request(
    change_request_id: int,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    return ProfileChangeRequestResponse.model_validate(
        service.approve(actor, change_request_id)
    )


@router.post(
    "/{change_request_id}/reject",
    response_model=ProfileChangeRequestResponse,
    summary="Superadmin: reject a profile edit request (ADR-032)",
)
def reject_change_request(
    change_request_id: int,
    data: RejectChangeRequestRequest,
    actor: CurrentUser,
    service: ProfileChangeService = Depends(get_profile_change_service),
):
    return ProfileChangeRequestResponse.model_validate(
        service.reject(actor, change_request_id, data.reason)
    )
