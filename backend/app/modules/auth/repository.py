"""auth repository (persistence only).

Owns all user_sessions SQLAlchemy queries. The raw session credential and
CSRF token NEVER pass through this layer — callers (the future ADR-P01
auth service) hash first with SHA-256 and pass only the digests.

Activity semantics: `touch` is the ONLY method that moves last_activity_at,
and it is explicit — never invoked by health checks, WebSocket
ping/pong, or background polling. It clamps to absolute_expires_at so
genuine activity can never extend the 12-hour absolute ceiling.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update

from app.modules.accounts.models import User
from app.modules.auth.models import UserSession
from app.modules.bases import BaseRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthRepository(BaseRepository[User]):
    """Owns credential-lookup and session-persistence queries only."""

    model = User

    # ------------------------------------------------------- lookups

    def find_user_by_identifier(self, identifier: str) -> User | None:
        """Look up a user by the approved login identifier.

        # TODO: Identifier policy (email vs student number) is part of ADR-P01.
        """
        return self.session.scalar(select(User).where(User.email == identifier))

    def find_session_by_token_hash(self, token_hash: bytes) -> UserSession | None:
        """Fetch a session row by credential digest (hash-then-lookup)."""
        return self.session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))

    def list_sessions_for_user(self, user_id: int, active_only: bool = False) -> list[UserSession]:
        """Sessions for one user, newest first; optionally only non-revoked."""
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        if active_only:
            stmt = stmt.where(UserSession.revoked_at.is_(None))
        return list(self.session.scalars(stmt.order_by(UserSession.created_at.desc())))

    # ------------------------------------------------------- writes

    def create_session(
        self,
        user_id: int,
        token_hash: bytes,
        csrf_token_hash: bytes,
        absolute_expires_at: datetime,
        *,
        created_at: datetime | None = None,
        last_activity_at: datetime | None = None,
    ) -> UserSession:
        """Insert one session row from pre-hashed credential values."""
        now = created_at if created_at is not None else utcnow()
        activity = last_activity_at if last_activity_at is not None else now
        session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            created_at=now,
            last_activity_at=activity,
            absolute_expires_at=absolute_expires_at,
        )
        self.session.add(session)
        self.session.flush()
        return session

    def touch_session(self, session_id: int, activity_at: datetime | None = None) -> None:
        """Record GENUINE user activity only (never heartbeats/polls).

        Clamps to absolute_expires_at — activity can refresh the idle
        window but never extend the absolute ceiling.
        """
        when = activity_at if activity_at is not None else utcnow()
        self.session.execute(
            update(UserSession)
            .where(
                UserSession.session_id == session_id,
                UserSession.revoked_at.is_(None),
            )
            .values(
                # Clamp: activity refreshes the idle window but can never
                # push last_activity_at past the absolute expiry ceiling.
                last_activity_at=func.least(UserSession.absolute_expires_at, when),
            )
        )

    def revoke_session(self, session_id: int, reason: str, *, revoked_at: datetime | None = None) -> int:
        """Revoke one session (logout, password reset, restriction).

        Returns the number of rows revoked (0 = already revoked or absent).
        """
        result = self.session.execute(
            update(UserSession)
            .where(
                UserSession.session_id == session_id,
                UserSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at if revoked_at is not None else utcnow(),
                revocation_reason=reason,
            )
        )
        return result.rowcount

    def revoke_all_sessions_for_user(
        self,
        user_id: int,
        reason: str,
        *,
        revoked_at: datetime | None = None,
        keep_session_id: int | None = None,
    ) -> int:
        """Revoke every live session for one user (disablement/single-session).

        `keep_session_id` spares one just-issued session (login replaces
        older sessions but keeps the newest one alive).
        """
        stmt = update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if keep_session_id is not None:
            stmt = stmt.where(UserSession.session_id != keep_session_id)
        result = self.session.execute(
            stmt.values(
                revoked_at=revoked_at if revoked_at is not None else utcnow(),
                revocation_reason=reason,
            )
        )
        return result.rowcount

    # ------------------------------------------------------- cleanup

    def delete_expired_sessions(self, *, now: datetime | None = None, keep_revoked_hours: int = 0) -> int:
        """Delete sessions eligible for removal; never touches users.

        Removes:
        - revoked sessions at least `keep_revoked_hours` old (audit window;
          0 deletes every revoked session),
        - sessions past absolute_expires_at.

        Returns the number of rows deleted.
        """
        moment = now if now is not None else utcnow()
        cutoff = moment - timedelta(hours=keep_revoked_hours)
        result = self.session.execute(
            delete(UserSession).where(
                (UserSession.absolute_expires_at < moment)
                | (
                    UserSession.revoked_at.is_not(None)
                    & (UserSession.revoked_at <= cutoff)
                )
            )
        )
        return result.rowcount
