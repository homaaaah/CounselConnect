"""Shared FastAPI dependencies (ADR-019 auth context).

- get_db_session: request-scoped Session (from app.database).
- get_current_user: authenticates the opaque session cookie, enforces
  the 1h idle / 12h absolute / CSRF rules, and touches genuine activity.
- require_roles: role gate for protected endpoints (backend authoritative).

Safe methods (GET/HEAD/OPTIONS) skip CSRF — the cookie is SameSite=Lax
and unsafe methods require the X-CSRF-Token header.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database import get_session
from app.modules.accounts.models import User
from app.modules.auth.service import SESSION_COOKIE, AuthService, get_auth_service

SessionDep = Annotated[Session, Depends(get_session)]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


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
    )
    if user.role_code != "COUNSELOR":
        raise AppError(
            code="FORBIDDEN_ROLE",
            message="Only a Guidance Counselor may perform this action.",
            status_code=403,
        )
    return user
