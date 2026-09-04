"""auth Pydantic contracts.

Request/response schemas are structural placeholders ONLY. Exact login
identifier policy and token/session response shape are pending ADR-P01.

# TODO: Implement after authentication/session mechanism is approved (ADR-P01).
"""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Placeholder shape; fields may change with ADR-P01."""

    identifier: str
    password: str


class AuthResponse(BaseModel):
    """Placeholder shape; fields may change with ADR-P01."""

    # TODO: Define after ADR-P01 (token/session fields unknown yet).
    pass
