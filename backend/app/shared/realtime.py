"""Shared authenticated WebSocket identity helpers (ADR-019/ADR-022).

WebSocket routes authenticate the same opaque session cookie as HTTP, require
an allowlisted Origin, and never renew the idle timer. Domain modules keep
their own authorization and delivery registries; this module only resolves
who is on the other end of the socket.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_engine
from app.modules.auth.service import SESSION_COOKIE, AuthService


@dataclass(frozen=True)
class SocketIdentity:
    user_id: int
    role_code: str
    account_status: str
    session_id: int


def origin_allowed(origin: str | None) -> bool:
    """True when the browser Origin is in the configured CORS allowlist."""
    return bool(origin and origin in get_settings().cors_origins)


def authenticate_socket(raw_credential: str | None) -> SocketIdentity:
    """Resolve a WebSocket's session cookie without recording user activity."""
    with Session(get_engine(), expire_on_commit=False) as session:
        actor, user_session = AuthService(session).authenticate_request(
            raw_credential, None, is_safe_method=True, record_activity=False
        )
        return SocketIdentity(
            actor.user_id,
            actor.role_code,
            actor.account_status,
            user_session.session_id,
        )


def socket_cookie(websocket: WebSocket) -> str | None:
    return websocket.cookies.get(SESSION_COOKIE)
