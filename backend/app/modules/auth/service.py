"""auth service: authorization + session rules (structure only).

# TODO: Implement after authentication/session mechanism is approved (ADR-P01).
Mechanism, tokens/sessions, and account-status gating rules are all pending.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.accounts.models import User
from app.modules.auth.repository import AuthRepository


class AuthService(BaseService[User]):
    """Login/session business rules.

    Must gate access on account_status and (for students) enrollment
    validity per docs/USER_ROLES.md — exact transport is pending ADR-P01.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(AuthRepository(session))


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return AuthService(session)
