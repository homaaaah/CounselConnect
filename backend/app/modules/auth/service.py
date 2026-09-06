"""auth service: login/session/CSRF business rules (ADR-019).

- Identifier: student number for Students, email for staff (ADR-005).
- Credential: 256-bit random opaque token; only its SHA-256 digest is
  stored/looked up (user_sessions).
- Sessions: 1h idle (last_activity_at), 12h absolute, never sliding;
  only genuine authenticated requests touch activity.
- Passwords: Argon2id; legacy bcrypt hashes verify then upgrade.
- Login is allowed for PENDING_VERIFICATION / ACTIVE / VERIFICATION_EXPIRED
  accounts (pending students must still reach their COR re-verification);
  feature-level ACTIVE gating stays with each feature's authorization.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    digests_match,
    hash_password,
    needs_rehash,
    new_session_credential,
    sha256_digest,
    session_csrf_token,
    verify_password,
)
from app.database import get_session
from app.modules.accounts.models import User
from app.modules.accounts.repository import AccountsRepository
from app.modules.auth.models import UserSession
from app.modules.auth.repository import AuthRepository
from app.modules.bases import BaseService

IDLE_TIMEOUT = timedelta(hours=1)
ABSOLUTE_LIFETIME = timedelta(hours=12)
SESSION_COOKIE = "counselconnect_session"
REVOCATION_LOGOUT = "USER_LOGOUT"
REVOCATION_REPLACED = "SESSION_REPLACED"
REVOCATION_ACCOUNT = "ACCOUNT_DISABLED"

_LOGIN_ALLOWED_STATUSES = ("PENDING_VERIFICATION", "ACTIVE", "VERIFICATION_EXPIRED")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """DB DATETIME values come back naive (UTC by connection convention)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class AuthService(BaseService[User]):
    """Login/session business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(AuthRepository(session))
        self.accounts = AccountsRepository(session)

    # ------------------------------------------------------------- helpers

    def _find_user_by_identifier(self, identifier: str) -> User | None:
        """Staff email takes precedence over any colliding student number.

        Students authenticate by student number (ADR-005/019); a public
        registration must never shadow a staff member's login identifier.
        """
        staff = self.accounts.find_user_by_email(identifier)
        if staff is not None and staff.role_code in ("GUIDANCE_STAFF", "COUNSELOR"):
            return staff
        profile = self.accounts.find_student_profile_by_number(identifier)
        if profile is not None:
            user = self.accounts.get(profile.user_id)
            if user is not None and user.role_code == "STUDENT":
                return user
        return None

    def _issue_session(self, user: User) -> tuple[UserSession, str, str]:
        """Create a session row; returns (row, raw_credential, raw_csrf)."""
        raw_credential = new_session_credential()
        raw_csrf = session_csrf_token(raw_credential)
        now = utcnow()
        session = UserSession(
            user_id=user.user_id,
            token_hash=sha256_digest(raw_credential),
            csrf_token_hash=sha256_digest(raw_csrf),
            created_at=now,
            last_activity_at=now,
            absolute_expires_at=now + ABSOLUTE_LIFETIME,
        )
        self.repository.session.add(session)
        self.repository.session.flush()
        return session, raw_credential, raw_csrf

    @staticmethod
    def _is_live(session: UserSession, *, now: datetime | None = None) -> bool:
        """Revoked, idle-expired, and absolute-expired sessions are dead."""
        moment = _as_utc(now or utcnow())
        if session.revoked_at is not None:
            return False
        if moment >= _as_utc(session.absolute_expires_at):
            return False
        if moment - _as_utc(session.last_activity_at) >= IDLE_TIMEOUT:
            return False
        return True

    # ------------------------------------------------------------- login

    def login(self, identifier: str, password: str) -> tuple[User, UserSession, str, str]:
        """Verify credentials and create a session.

        Returns (user, session_row, raw_credential, raw_csrf_token). The
        raw session credential goes ONLY into the Set-Cookie header via
        set_session_cookie(); it is never logged, stored, or returned in
        a response body.
        """
        user = self._find_user_by_identifier(identifier)
        if user is None:
            # Timing parity: unknown identifiers run a dummy verify so
            # response time cannot reveal whether the identifier exists.
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="Incorrect identifier or password.",
                status_code=401,
            )
        if not verify_password(password, user.password_hash):
            # Same error either way: never reveal which part failed.
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="Incorrect identifier or password.",
                status_code=401,
            )
        if user.account_status not in _LOGIN_ALLOWED_STATUSES:
            raise AppError(
                code="ACCOUNT_NOT_LOGINABLE",
                message="This account cannot sign in in its current state.",
                status_code=403,
            )

        # Transparent bcrypt → Argon2id upgrade on successful login.
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        session, raw_credential, raw_csrf = self._issue_session(user)
        # Single-session policy: revoke other live sessions for this user.
        self.repository.revoke_all_sessions_for_user(
            user.user_id, REVOCATION_REPLACED, keep_session_id=session.session_id
        )
        return user, session, raw_credential, raw_csrf

    # ---------------------------------------------------------- cookie jar

    def set_session_cookie(self, response: Response, raw_credential: str) -> None:
        """Secure HttpOnly session cookie (ADR-019).

        `secure` is True in HTTPS deployments (COUNSELCONNECT_COOKIE_SECURE);
        localhost dev uses False so the browser accepts the cookie.
        """
        from app.config import get_settings

        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            key=SESSION_COOKIE,
            value=raw_credential,
            max_age=int(ABSOLUTE_LIFETIME.total_seconds()),
            httponly=True,
            samesite="lax",
            secure=get_settings().cookie_secure,
            path="/",
        )

    def clear_session_cookie(self, response: Response) -> None:
        response.delete_cookie(key=SESSION_COOKIE, path="/")

    def recover_csrf_token(self, session: UserSession, raw_credential: str) -> str:
        """Recover the same token across reloads/tabs; upgrade legacy tokens once."""
        raw_csrf = session_csrf_token(raw_credential)
        digest = sha256_digest(raw_csrf)
        if not digests_match(session.csrf_token_hash, digest):
            session.csrf_token_hash = digest
            self.repository.session.flush()
        return raw_csrf

    # ----------------------------------------------------- current user

    def authenticate_request(
        self, raw_credential: str | None, csrf_token: str | None, *, is_safe_method: bool,
        record_activity: bool = True,
    ) -> tuple[User, UserSession]:
        """Authenticate one request; enforce idle/absolute/CSRF rules.

        Genuine authenticated requests touch last_activity_at (clamped to
        the absolute ceiling); public endpoints never call this.
        """
        if raw_credential is None:
            raise AppError(
                code="NOT_AUTHENTICATED",
                message="Sign in to continue.",
                status_code=401,
            )
        session = self.repository.find_session_by_token_hash(sha256_digest(raw_credential))
        if session is None or not self._is_live(session):
            raise AppError(
                code="SESSION_INVALID",
                message="Your session is invalid or has expired. Sign in again.",
                status_code=401,
            )
        if not is_safe_method:
            provided = sha256_digest(csrf_token or "")
            if not digests_match(session.csrf_token_hash, provided):
                raise AppError(
                    code="CSRF_TOKEN_INVALID",
                    message="Request blocked: missing or invalid CSRF token.",
                    status_code=403,
                )
        user = self.accounts.get(session.user_id)
        if user is None or user.account_status not in _LOGIN_ALLOWED_STATUSES:
            # Account disabled/restricted after login: kill the session.
            self.repository.revoke_session(session.session_id, REVOCATION_ACCOUNT)
            raise AppError(
                code="ACCOUNT_NOT_LOGINABLE",
                message="This account cannot continue in its current state.",
                status_code=403,
            )
        # Genuine user action renews the idle window (never past the ceiling).
        if record_activity:
            self.repository.touch_session(session.session_id)
        return user, session

    # ------------------------------------------------------------- logout

    def logout(self, raw_credential: str | None) -> None:
        if raw_credential is None:
            return  # idempotent: no cookie, nothing to revoke
        session = self.repository.find_session_by_token_hash(sha256_digest(raw_credential))
        if session is not None and session.revoked_at is None:
            self.repository.revoke_session(session.session_id, REVOCATION_LOGOUT)


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return AuthService(session)
