"""auth router: /auth/login|refresh|logout (ADR-019).

Opaque session cookie flow:
- POST /auth/login    → verifies credentials, sets HttpOnly cookie,
                        returns user + CSRF token + expiry timestamps.
- POST /auth/refresh  → revalidates the session (CSRF required), returns
                        current user + fresh CSRF + expiry timestamps.
- POST /auth/logout   → revokes the session (CSRF required), clears cookie.
- GET  /auth/me       → current authenticated user (safe method, no CSRF).

Route names follow NAMING_CONVENTIONS.md auth exceptions.
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response

from app.modules.auth.schemas import AuthResponse, LoginRequest, SessionUser
from app.modules.auth.service import SESSION_COOKIE, AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _csrf_from(request: Request) -> str | None:
    return request.headers.get("X-CSRF-Token")


def _iso_utc(value) -> str:
    from app.modules.auth.service import _as_utc

    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _auth_response(user, session, csrf_token: str) -> AuthResponse:
    from app.modules.auth.service import IDLE_TIMEOUT, _as_utc

    return AuthResponse(
        user=SessionUser.model_validate(user, from_attributes=True),
        csrf_token=csrf_token,
        # Idle-expiry MOMENT (last activity + 1h), not last-activity time —
        # the frontend warns at five minutes before this (FR-AUTH-03).
        idle_expires_at=_iso_utc(_as_utc(session.last_activity_at) + IDLE_TIMEOUT),
        absolute_expires_at=_iso_utc(session.absolute_expires_at),
    )


@router.post("/login", response_model=AuthResponse, summary="Sign in (student number or staff email)")
def login(
    data: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    user, session, raw_credential, raw_csrf = service.login(data.identifier, data.password)
    service.set_session_cookie(response, raw_credential)
    return _auth_response(user, session, raw_csrf)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Revalidate the current session (CSRF header required)",
)
def refresh(
    request: Request,
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    service: AuthService = Depends(get_auth_service),
):
    user, session = service.authenticate_request(
        session_cookie, _csrf_from(request), is_safe_method=False
    )
    # The caller proved CSRF possession via the header; echo it back so
    # reconnecting clients can restore their in-memory copy.
    csrf_token = _csrf_from(request) or ""
    service.set_session_cookie(response, session_cookie or "")
    return _auth_response(user, session, csrf_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Sign out and revoke the session (CSRF header required)",
)
def logout(
    request: Request,
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    service: AuthService = Depends(get_auth_service),
):
    service.authenticate_request(session_cookie, _csrf_from(request), is_safe_method=False)
    service.logout(session_cookie)
    service.clear_session_cookie(response)


@router.get("/me", response_model=SessionUser, summary="Current authenticated user")
def me(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    service: AuthService = Depends(get_auth_service),
):
    response.headers["Cache-Control"] = "no-store"
    user, _session = service.authenticate_request(
        session_cookie, None, is_safe_method=True, record_activity=False
    )
    return SessionUser.model_validate(user, from_attributes=True)


@router.get(
    "/csrf",
    response_model=AuthResponse,
    summary="Recover the CSRF token for a live session without renewing idle activity",
)
def recover_csrf(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    service: AuthService = Depends(get_auth_service),
):
    """Recovers the session-bound CSRF token after a page reload.

    Safe because the caller must already hold the session cookie (proof
    of the credential); CSRF tokens are not secrets from their own
    session — they only guard cross-site forgery of unsafe requests.
    """
    response.headers["Cache-Control"] = "no-store"
    user, session = service.authenticate_request(
        session_cookie, None, is_safe_method=True, record_activity=False
    )
    raw_csrf = service.recover_csrf_token(session, session_cookie)
    return _auth_response(user, session, raw_csrf)
