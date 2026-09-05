"""Password and credential hashing primitives (ADR-019).

- New/updated passwords hash with Argon2id (argon2-cffi).
- Legacy bcrypt hashes still verify; a successful bcrypt login rehashes
  with Argon2id and updates the stored hash (transparent upgrade).
- Session/CSRF credentials are random 256-bit values; only their
  SHA-256 digests are stored or compared (digest lookups are index
  lookups; verification uses constant-time compares on digest bytes).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_argon2 = PasswordHasher()  # argon2-cffi defaults: Argon2id, 64 MiB, t=3, p=4

# Raw opaque credentials carry at least 256 bits of entropy (ADR-019).
CREDENTIAL_ENTROPY_BYTES = 32
SHA256_DIGEST_BYTES = 32


# ------------------------------------------------------------------ passwords


def hash_password(plain: str) -> str:
    """Hash a password with Argon2id."""
    return _argon2.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """True when the password matches an Argon2id or legacy bcrypt hash."""
    if hashed.startswith("$argon2"):
        try:
            return _argon2.verify(hashed, plain)
        except VerifyMismatchError:
            return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def needs_rehash(hashed: str) -> bool:
    """True when a stored hash is bcrypt (or weak Argon2) and should upgrade."""
    if hashed.startswith("$argon2"):
        return _argon2.check_needs_rehash(hashed)
    return True  # bcrypt → Argon2id


# ------------------------------------------------------------------ sessions


def new_session_credential() -> str:
    """New 256-bit random opaque session credential (urlsafe text)."""
    return secrets.token_urlsafe(CREDENTIAL_ENTROPY_BYTES)


def new_csrf_token() -> str:
    """New 256-bit random CSRF token bound to one session."""
    return secrets.token_urlsafe(CREDENTIAL_ENTROPY_BYTES)


def sha256_digest(value: str) -> bytes:
    """SHA-256 digest of a credential (what user_sessions stores)."""
    return hashlib.sha256(value.encode("utf-8")).digest()


def digests_match(expected: bytes, provided: bytes) -> bool:
    """Constant-time comparison of two fixed-length digests."""
    return hmac.compare_digest(expected, provided)
