"""auth repository (persistence only).

# TODO: Implement after authentication/session mechanism is approved (ADR-P01).
"""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.accounts.models import User


class AuthRepository(BaseRepository[User]):
    """Owns credential-lookup queries only."""

    model = User

    def find_user_by_identifier(self, identifier: str) -> User | None:
        """Look up a user by the approved login identifier.

        # TODO: Identifier policy (email vs student number) is part of ADR-P01.
        """
        return self.session.scalar(select(User).where(User.email == identifier))
