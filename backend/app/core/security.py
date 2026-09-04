"""Password hashing primitives (bcrypt).

Only the low-level hashing helpers live here so account creation can store
hashes with the project's chosen algorithm. The authentication/session
mechanism itself is pending decision ADR-P01 and is NOT implemented.

# TODO: Implement after authentication/session mechanism is approved (ADR-P01).
"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
