"""Shared FastAPI dependencies (ADR-019 auth context).

- get_db_session: request-scoped Session (from app.database).
- get_current_user: authenticates the opaque session cookie, enforces
  the 1h idle / 12h absolute / CSRF rules, and touches genuine activity.
- require_roles: role gate for protected endpoints (backend authoritative).

Safe methods (GET/HEAD/OPTIONS) skip CSRF — the cookie is SameSite=Lax
and unsafe methods require the X-CSRF-Token header.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database import get_session
from app.modules.accounts.models import User
from app.modules.auth.service import SESSION_COOKIE, AuthService, get_auth_service
from app.modules.cor_screening.models import CorScreening
from app.modules.cor_screening.service import (
    CorScreeningService,
    get_cor_screening_service,
)

SessionDep = Annotated[Session, Depends(get_session)]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# One-time in-modal COR verification token; alternative to a Student session.
COR_TOKEN_HEADER = "X-COR-Token"


def get_current_user(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Authenticate the request; returns the acting User (backend authority)."""
    user, _session = auth_service.authenticate_request(
        session_cookie,
        request.headers.get("X-CSRF-Token"),
        is_safe_method=request.method.upper() in _SAFE_METHODS,
        record_activity=request.headers.get("X-Background-Refresh") != "1",
    )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class require_roles:  # noqa: N801 — used as a dependency factory
    """Endpoint dependency: caller must be authenticated with one of `roles`."""

    def __init__(self, *roles: str) -> None:
        self.roles = frozenset(roles)

    def __call__(
        self,
        request: Request,
        session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> User:
        user, _session = auth_service.authenticate_request(
            session_cookie,
            request.headers.get("X-CSRF-Token"),
            is_safe_method=request.method.upper() in _SAFE_METHODS,
            record_activity=request.headers.get("X-Background-Refresh") != "1",
        )
        if user.role_code not in self.roles:
            raise AppError(
                code="FORBIDDEN_ROLE",
                message="You do not have permission to perform this action.",
                status_code=403,
            )
        return user


def require_counselor(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """COUNSELOR-only guard (highest authority; there is no admin role)."""
    user, _session = auth_service.authenticate_request(
        session_cookie,
        request.headers.get("X-CSRF-Token"),
        is_safe_method=request.method.upper() in _SAFE_METHODS,
        record_activity=request.headers.get("X-Background-Refresh") != "1",
    )
    if user.role_code != "COUNSELOR":
        raise AppError(
            code="FORBIDDEN_ROLE",
            message="Only a Guidance Counselor may perform this action.",
            status_code=403,
        )
    return user


@dataclass
class ScreeningActor:
    """Resolved caller for a confirm/reject/resubmit action.

    `screening` is set only when the one-time token authenticated the request
    (the Student row and screening are already locked); None means the caller
    authenticated with a Student session and the service must resolve state.
    """

    user: User
    screening: CorScreening | None = None


def get_screening_actor(
    request: Request,
    cor_token: str | None = Header(default=None, alias=COR_TOKEN_HEADER),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth_service: AuthService = Depends(get_auth_service),
    service: CorScreeningService = Depends(get_cor_screening_service),
) -> ScreeningActor:
    """Authorize a Student action by one-time token OR Student session.

    A present-but-invalid token fails closed (never falls back to the session);
    token requests are cookie-less, so CSRF does not apply. The raw token is
    never logged.
    """
    if cor_token is not None:
        user, screening = service.resolve_verification_token(cor_token)
        return ScreeningActor(user=user, screening=screening)
    user, _session = auth_service.authenticate_request(
        session_cookie,
        request.headers.get("X-CSRF-Token"),
        is_safe_method=request.method.upper() in _SAFE_METHODS,
        record_activity=request.headers.get("X-Background-Refresh") != "1",
    )
    if user.role_code != "STUDENT":
        raise AppError(
            code="FORBIDDEN_ROLE",
            message="You do not have permission to perform this action.",
            status_code=403,
        )
    return ScreeningActor(user=user)
