"""auth router: /auth/login|refresh|logout (structure only).

Route names follow NAMING_CONVENTIONS.md auth exceptions. Login verifies
credentials but the session/token mechanism is pending decision ADR-P01 —
the endpoint returns a structured AUTH_MECHANISM_PENDING error rather than
an invented token/cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.exceptions import AppError
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Sign in (session mechanism pending ADR-P01)")
def login(
    data: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    # Credential verification arrives with ADR-P01; no token/cookie/session
    # is invented here.
    raise AppError(
        code="AUTH_MECHANISM_PENDING",
        message="Authentication mechanism is pending decision ADR-P01.",
        status_code=501,
    )


@router.post("/refresh", summary="Refresh session (pending ADR-P01)")
def refresh(service: AuthService = Depends(get_auth_service)):
    raise AppError(
        code="AUTH_MECHANISM_PENDING",
        message="Authentication mechanism is pending decision ADR-P01.",
        status_code=501,
    )


@router.post("/logout", summary="Sign out (pending ADR-P01)")
def logout(service: AuthService = Depends(get_auth_service)):
    raise AppError(
        code="AUTH_MECHANISM_PENDING",
        message="Authentication mechanism is pending decision ADR-P01.",
        status_code=501,
    )
