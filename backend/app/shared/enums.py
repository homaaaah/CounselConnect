"""Approved enum values ONLY (NAMING_CONVENTIONS.md — do not invent values).

These constants document the approved states; they are not a replacement for
database CHECK constraints. Persistence uses plain String columns matching
the v4 SQL, with these constants as the source of allowed values in code.
"""

from __future__ import annotations

from enum import Enum

# Roles (docs/USER_ROLES.md) — no ADMIN role exists or may be introduced.
ROLE_STUDENT = "STUDENT"
ROLE_GUIDANCE_STAFF = "GUIDANCE_STAFF"
ROLE_COUNSELOR = "COUNSELOR"

ACCOUNT_STATUSES = ("PENDING_VERIFICATION", "ACTIVE", "VERIFICATION_EXPIRED")
VERIFICATION_STATUSES = ("PENDING", "APPROVED", "NEEDS_RESUBMISSION", "REJECTED", "EXPIRED")
AVAILABILITY_STATUSES = ("AVAILABLE", "RESERVED")
DELIVERY_MODES = ("ONLINE", "FACE_TO_FACE", "BOTH")
APPOINTMENT_MODES = ("ONLINE", "FACE_TO_FACE")
APPOINTMENT_STATUSES = ("PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "REJECTED", "NO_SHOW")
CONVERSATION_TYPES = ("GENERAL", "APPOINTMENT", "SOS")
CONVERSATION_STATUSES = ("OPEN", "CLOSED")
SOS_CASE_STATUSES = ("OPEN", "RESPONDED", "CLOSED")
WELLNESS_RESOURCE_STATUSES = ("PENDING", "PUBLISHED", "REJECTED", "DISABLED")


class Role(str, Enum):
    STUDENT = ROLE_STUDENT
    GUIDANCE_STAFF = ROLE_GUIDANCE_STAFF
    COUNSELOR = ROLE_COUNSELOR
