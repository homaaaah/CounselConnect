"""Focused tests for the user_sessions model, repository, and migration.

Covers (task acceptance criteria):
1.  Migration upgrade creates user_sessions with expected columns, types,
    FK, unique constraint, and indexes on the real MySQL test schema.
2.  Migration downgrade removes only user_sessions and its own objects.
3.  Duplicate token_hash is rejected.
4.  A session cannot reference a nonexistent user.
5.  Create + lookup by token hash works without exposing raw credentials.
6.  Genuine activity updates last_activity_at but cannot extend
    absolute_expires_at (clamp + timeline CHECK).
7.  Idle-expired, absolute-expired, and revoked sessions are inactive
    (repository classification for the future auth service).
8.  Revoke-one and revoke-all-for-user operations work.
9.  Cleanup removes eligible expired/revoked sessions without deleting users.
10. UTC-aware application values round-trip through MySQL DATETIME(6).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.accounts.models import User
from app.modules.auth.models import UserSession
from app.modules.auth.repository import AuthRepository

from ..conftest import load_migration_module

# Policy constants (task contract; final mechanism still pending ADR-P01).
IDLE_TIMEOUT = timedelta(hours=1)
ABSOLUTE_LIFETIME = timedelta(hours=12)


def sha256(raw: bytes) -> bytes:
    return hashlib.sha256(raw).digest()


def as_utc(value: datetime) -> datetime:
    """MySQL DATETIME comes back naive; the project convention is UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@pytest.fixture()
def repo(db_session):
    return AuthRepository(db_session)


@pytest.fixture()
def user(db_session) -> User:
    """A real MySQL user row so FK integrity is genuinely exercised."""
    import uuid

    suffix = uuid.uuid4().hex[:8]
    u = User(
        email=f"sess-{suffix}@example.edu",
        password_hash="bcrypt-placeholder",
        role_code="STUDENT",
        account_status="ACTIVE",
        first_name="Juan",
        last_name="Dela Cruz",
    )
    db_session.add(u)
    db_session.flush()
    return u


def make_session(
    repo: AuthRepository,
    user_id: int,
    *,
    token: bytes | None = None,
    csrf: bytes | None = None,
    created_at: datetime | None = None,
    absolute_expires_at: datetime | None = None,
) -> UserSession:
    """Create a session with pre-hashed credentials (as the auth service will)."""
    token = token or sha256(b"raw-opaque-credential-" + (user_id.to_bytes(8, "big")) + b"-1")
    csrf = csrf or sha256(b"raw-csrf-token")
    now = created_at or datetime.now(timezone.utc)
    return repo.create_session(
        user_id,
        sha256(token) if len(token) != 32 else token,
        csrf,
        absolute_expires_at or now + ABSOLUTE_LIFETIME,
        created_at=now,
    )


# ---------------------------------------------------------------------------
# 1. Migration upgrade shape (verified against live MySQL schema)
# ---------------------------------------------------------------------------


def test_migration_upgrade_creates_expected_table(mysql_test_engine):
    with mysql_test_engine.connect() as conn:
        cols = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = :d AND table_name = 'user_sessions' ORDER BY ordinal_position"
            ),
            {"d": mysql_test_engine.url.database},
        ).fetchall()
        checks = conn.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_schema = :d AND table_name = 'user_sessions' "
                "AND constraint_type IN ('CHECK', 'FOREIGN KEY', 'UNIQUE')"
            ),
            {"d": mysql_test_engine.url.database},
        ).fetchall()
        indexes = conn.execute(
            text(
                "SELECT index_name, non_unique FROM information_schema.statistics "
                "WHERE table_schema = :d AND table_name = 'user_sessions' GROUP BY index_name, non_unique"
            ),
            {"d": mysql_test_engine.url.database},
        ).fetchall()

    colmap = {(name, dtype): nullable for (name, dtype, nullable) in cols}
    assert ("session_id", "bigint") in colmap
    assert ("user_id", "bigint") in colmap
    assert ("token_hash", "binary") in colmap
    assert ("csrf_token_hash", "binary") in colmap
    assert ("revoked_at", "datetime") in colmap
    assert ("revocation_reason", "varchar") in colmap
    assert colmap[("created_at", "datetime")] == "NO"
    assert colmap[("last_activity_at", "datetime")] == "NO"
    assert colmap[("absolute_expires_at", "datetime")] == "NO"
    assert colmap[("token_hash", "binary")] == "NO"
    # Unsigned BIGINT PK/FK and BINARY(32) fixed length via full column type.
    with mysql_test_engine.connect() as conn:
        details = conn.execute(
            text(
                "SELECT column_name, column_type FROM information_schema.columns "
                "WHERE table_schema = :d AND table_name = 'user_sessions' "
                "AND column_name IN ('session_id', 'user_id', 'token_hash')"
            ),
            {"d": mysql_test_engine.url.database},
        ).fetchall()
    typemap = {name: ctype for (name, ctype) in details}
    assert typemap["session_id"] == "bigint unsigned"
    assert typemap["user_id"] == "bigint unsigned"
    assert typemap["token_hash"] == "binary(32)"

    check_names = {row[0] for row in checks}
    assert "chk_user_sessions_timeline" in check_names
    assert "chk_user_sessions_revocation_shape" in check_names
    assert "uq_user_sessions_token_hash" in check_names
    assert "fk_user_sessions_user" in check_names

    index_names = {row[0] for row in indexes}
    assert "idx_user_sessions_user_active" in index_names
    assert "idx_user_sessions_cleanup" in index_names

    with mysql_test_engine.connect() as conn:
        fk = conn.execute(
            text(
                "SELECT delete_rule, update_rule FROM information_schema.referential_constraints "
                "WHERE constraint_schema = :d AND constraint_name = 'fk_user_sessions_user'"
            ),
            {"d": mysql_test_engine.url.database},
        ).fetchone()
    assert fk == ("CASCADE", "CASCADE")


# ---------------------------------------------------------------------------
# 2. Migration downgrade removes only user_sessions (run on a scratch schema)
# ---------------------------------------------------------------------------


def test_migration_downgrade_drops_only_user_sessions(mysql_test_engine):
    """Downgrade via the migration's own code; verify only its objects vanish."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = load_migration_module()

    def table_names(conn):
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :d"),
            {"d": mysql_test_engine.url.database},
        ).fetchall()
        return {r[0] for r in rows}

    with mysql_test_engine.connect() as conn:
        before = table_names(conn)
        assert "user_sessions" in before

        # DDL implicitly commits in MySQL; run via the migration's own code.
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.downgrade()
        after = table_names(conn)
        # Only user_sessions removed; every other table still present.
        assert "user_sessions" not in after
        assert after == before - {"user_sessions"}

        # Upgrade again to restore head for the rest of the suite.
        with Operations.context(ctx):
            migration.upgrade()
        assert table_names(conn) == before


# ---------------------------------------------------------------------------
# 3. Duplicate token_hash rejected
# ---------------------------------------------------------------------------


def test_duplicate_token_hash_rejected(db_session, repo, user):
    digest = sha256(b"unique-credential")
    make_session(repo, user.user_id, token=digest)
    db_session.flush()

    other = UserSession(
        user_id=user.user_id,
        token_hash=digest,
        csrf_token_hash=sha256(b"other-csrf"),
        created_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc),
        absolute_expires_at=datetime.now(timezone.utc) + ABSOLUTE_LIFETIME,
    )
    db_session.add(other)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------------------------------
# 4. FK integrity: session cannot reference nonexistent user
# ---------------------------------------------------------------------------


def test_session_cannot_reference_nonexistent_user(db_session, repo):
    now = datetime.now(timezone.utc)
    ghost = UserSession(
        user_id=987654321,
        token_hash=sha256(b"ghost-credential"),
        csrf_token_hash=sha256(b"ghost-csrf"),
        created_at=now,
        last_activity_at=now,
        absolute_expires_at=now + ABSOLUTE_LIFETIME,
    )
    db_session.add(ghost)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------------------------------
# 5. Create + lookup by hash; raw credential never stored
# ---------------------------------------------------------------------------


def test_create_and_lookup_by_token_hash(db_session, repo, user):
    raw_credential = b"super-secret-opaque-credential-material"
    digest = sha256(raw_credential)
    created = make_session(repo, user.user_id, token=digest)
    db_session.flush()

    found = repo.find_session_by_token_hash(digest)
    assert found is not None
    assert found.session_id == created.session_id
    assert found.user_id == user.user_id
    # Only digests stored — the raw credential is not recoverable.
    assert found.token_hash == digest
    assert found.token_hash != raw_credential
    assert len(found.token_hash) == 32
    # Unknown credential hash misses.
    assert repo.find_session_by_token_hash(sha256(b"unknown")) is None


# ---------------------------------------------------------------------------
# 6. Activity updates last_activity_at but never extends absolute_expires_at
# ---------------------------------------------------------------------------


def test_touch_updates_activity_without_extending_absolute_expiry(db_session, repo, user):
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    session = make_session(repo, user.user_id, created_at=created_at)
    db_session.flush()

    later = created_at + timedelta(minutes=30)
    repo.touch_session(session.session_id, activity_at=later)
    db_session.flush()
    db_session.refresh(session)
    # MySQL DATETIME returns naive values; the project convention is to
    # interpret them as UTC (connection time zone is forced to +00:00).
    assert session.last_activity_at == later.replace(tzinfo=None)
    assert as_utc(session.absolute_expires_at) == created_at + ABSOLUTE_LIFETIME

    # Activity AFTER the absolute ceiling clamps to the ceiling.
    after_ceiling = created_at + ABSOLUTE_LIFETIME + timedelta(hours=2)
    repo.touch_session(session.session_id, activity_at=after_ceiling)
    db_session.flush()
    db_session.refresh(session)
    assert as_utc(session.last_activity_at) == as_utc(session.absolute_expires_at)


# ---------------------------------------------------------------------------
# 7. Idle/absolute/revoked sessions are inactive
# ---------------------------------------------------------------------------


def session_is_active(s: UserSession, *, now: datetime | None = None) -> bool:
    """The classification the future auth service will apply (task contract).

    DB datetimes come back naive (UTC by connection convention); normalize
    before comparing against aware values.
    """
    moment = now or datetime.now(timezone.utc)

    if s.revoked_at is not None:
        return False
    if moment >= as_utc(s.absolute_expires_at):
        return False
    if moment - as_utc(s.last_activity_at) >= IDLE_TIMEOUT:
        return False
    return True


def test_idle_expired_absolute_expired_and_revoked_sessions_inactive(db_session, repo, user):
    now = datetime.now(timezone.utc).replace(microsecond=0)

    fresh = make_session(repo, user.user_id, created_at=now)

    idle = make_session(
        repo,
        user.user_id,
        token=sha256(b"raw-idle"),
        created_at=now - timedelta(hours=3),
        absolute_expires_at=now + ABSOLUTE_LIFETIME,
    )
    # Simulate last activity 2 hours ago by direct update (idle > 1h).
    idle.last_activity_at = now - timedelta(hours=2)
    repo.touch_session(idle.session_id, activity_at=now - timedelta(hours=2))

    expired = make_session(
        repo,
        user.user_id,
        token=sha256(b"raw-absolute"),
        created_at=now - timedelta(hours=13),
        absolute_expires_at=now - timedelta(hours=1),
    )
    # last_activity long ago; also absolute window passed.

    revoked = make_session(repo, user.user_id, token=sha256(b"raw-revoked"), created_at=now)
    repo.revoke_session(revoked.session_id, "USER_LOGOUT", revoked_at=now)
    db_session.flush()
    # Bulk UPDATE bypasses the identity map — force a fresh read.
    db_session.expire_all()

    assert session_is_active(fresh, now=now)
    assert not session_is_active(idle, now=now)
    assert not session_is_active(expired, now=now)
    assert not session_is_active(revoked, now=now)


# ---------------------------------------------------------------------------
# 8. Revoke-one and revoke-all
# ---------------------------------------------------------------------------


def test_revoke_one_and_revoke_all_for_user(db_session, repo, user):
    now = datetime.now(timezone.utc)
    s1 = make_session(repo, user.user_id, token=sha256(b"raw-1"), created_at=now)
    s2 = make_session(repo, user.user_id, token=sha256(b"raw-2"), created_at=now)
    s3 = make_session(repo, user.user_id, token=sha256(b"raw-3"), created_at=now)
    db_session.flush()

    # Revoke one: exactly that session, others untouched.
    assert repo.revoke_session(s2.session_id, "USER_LOGOUT") == 1
    db_session.flush()
    db_session.refresh(s2)
    assert s2.revoked_at is not None
    assert s2.revocation_reason == "USER_LOGOUT"
    assert repo.revoke_session(s2.session_id, "USER_LOGOUT") == 0  # idempotent

    # Revoke all remaining for the user.
    assert repo.revoke_all_sessions_for_user(user.user_id, "ACCOUNT_DISABLED") == 2
    db_session.flush()
    for s in (s1, s2, s3):
        db_session.refresh(s)
        assert s.revoked_at is not None
    assert {s1.revocation_reason, s2.revocation_reason, s3.revocation_reason} == {
        "ACCOUNT_DISABLED",
        "USER_LOGOUT",
    }
    assert repo.revoke_all_sessions_for_user(user.user_id, "ACCOUNT_DISABLED") == 0


# ---------------------------------------------------------------------------
# 9. Cleanup removes expired/revoked sessions without deleting users
# ---------------------------------------------------------------------------


def test_cleanup_removes_eligible_sessions_keeps_users(db_session, repo, user):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    keep_live = make_session(repo, user.user_id, token=sha256(b"live"), created_at=now)
    expired = make_session(
        repo,
        user.user_id,
        token=sha256(b"gone-expired"),
        created_at=now - timedelta(hours=13),
        absolute_expires_at=now - timedelta(hours=1),
    )
    revoked = make_session(repo, user.user_id, token=sha256(b"gone-revoked"), created_at=now)
    repo.revoke_session(revoked.session_id, "USER_LOGOUT", revoked_at=now)
    db_session.flush()

    assert user.user_id is not None
    deleted = repo.delete_expired_sessions(now=now)
    assert deleted == 2  # expired + revoked
    db_session.flush()
    # Bulk deletes bypass the identity map — expire before re-reading.
    db_session.expire_all()

    assert db_session.get(UserSession, keep_live.session_id) is not None
    # Deleted rows: get() raises ObjectDeletedError on expired instances,
    # so query by token hash instead.
    assert repo.find_session_by_token_hash(sha256(b"gone-expired")) is None
    assert repo.find_session_by_token_hash(sha256(b"gone-revoked")) is None
    # User untouched.
    still_here = db_session.get(User, user.user_id)
    assert still_here is not None and still_here.email == user.email


# ---------------------------------------------------------------------------
# 10. UTC round-trip through DATETIME(6)
# ---------------------------------------------------------------------------


def test_utc_datetimes_round_trip(db_session, repo, user):
    created = datetime.now(timezone.utc).replace(microsecond=123456)
    session = make_session(repo, user.user_id, created_at=created)
    session.absolute_expires_at = created + ABSOLUTE_LIFETIME
    db_session.flush()
    db_session.expire_all()

    found = repo.find_session_by_token_hash(session.token_hash)
    assert found.created_at.replace(tzinfo=timezone.utc) == created
    assert found.absolute_expires_at.replace(tzinfo=timezone.utc) == created + ABSOLUTE_LIFETIME
    # Microsecond precision survives (DATETIME(6)).
    assert found.created_at.microsecond == 123456
