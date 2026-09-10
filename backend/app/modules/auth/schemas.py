"""auth Pydantic contracts (ADR-019).

Login accepts one identifier: students use their student number, staff
use their email (ADR-005). Responses carry the CSRF token (safe to expose
to the authenticated caller; it must accompany unsafe-method requests)
and both expiry timestamps so the frontend can render the five-minute
idle warning (FR-AUTH-03).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class SessionUser(BaseModel):
    user_id: int
    email: str
    role_code: str
    account_status: str
    first_name: str
    last_name: str


class AuthResponse(BaseModel):
    user: SessionUser
    csrf_token: str
    idle_expires_at: str
    absolute_expires_at: str
