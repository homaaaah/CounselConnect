"""Shared FastAPI dependencies.

- get_db_session: request-scoped Session (from app.database).
- get_current_user: PLACEHOLDER ONLY. The authentication/session mechanism
  is pending decision ADR-P01. Do not implement JWT, cookies, Bearer tokens,
  refresh tokens, or OAuth here.

# TODO: Implement after authentication/session mechanism is approved (ADR-P01).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user():  # noqa: ANN201 - placeholder signature pending ADR-P01
    """Placeholder current-user dependency.

    Raises:
        NotImplementedError: always, until ADR-P01 approves a mechanism.
    """
    raise NotImplementedError(
        "Authentication dependency pending ADR-P01 (auth mechanism decision)."
    )
