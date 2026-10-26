"""Read-only protected identity checks and safe database failure outcomes."""

from types import SimpleNamespace

import pytest
from pymysql.err import IntegrityError as MysqlIntegrityError, OperationalError as MysqlOperationalError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.modules.accounts.models import StudentProfile, User
from app.modules.accounts.repository import AccountsRepository
from app.modules.audit.models import AuditEvent
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf


def approve(client, row):
    return client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/approve",
                       headers=csrf(client), json={"submission_version": 1})


def unchanged(db, values):
    _, user, _, profile, row, _, path = values
    db.refresh(user)
    db.refresh(profile)
    db.refresh(row)
    assert (user.first_name, user.last_name, user.account_status) == ("Juan", "Cruz", "ACTIVE")
    assert (profile.student_number, profile.year_level, profile.section) == ("20231234-A", 1, "A")
    assert row.status == "PENDING" and row.reviewed_at is row.reviewed_by_user_id is None
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "profile_change_approved")) == 0
    assert path.exists()


@pytest.mark.parametrize("identity", ["email", "student_number"])
@pytest.mark.parametrize("result", [None, SimpleNamespace(user_id=999999)])
def test_missing_or_different_identity_owner_is_safe_stale(db_session, db_client, evidence, monkeypatch, identity, result):
    method = "find_user_by_email" if identity == "email" else "find_student_profile_by_number"
    reads = []

    def lookup(self, value, *, lock=False):
        reads.append(lock)
        return result

    monkeypatch.setattr(AccountsRepository, method, lookup)
    response = approve(db_client, evidence[4])
    assert response.status_code == 409 and reads == [True]
    assert response.json()["error"]["code"] == "CHANGE_REQUEST_STALE"
    assert response.json()["error"]["details"] == {}
    assert "999999" not in response.text
    unchanged(db_session, evidence)


def test_success_rechecks_both_identifiers_with_current_locks_and_never_rewrites_them(db_session, db_client, evidence):
    _, user, _, profile, row, _, _ = evidence
    identity = user.email, profile.student_number
    reads, writes = [], []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if "FOR UPDATE" in statement and ("users.email =" in statement or "student_profiles.student_number =" in statement):
            reads.append(statement)
        if statement.startswith("UPDATE users") or statement.startswith("UPDATE student_profiles"):
            writes.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        response = approve(db_client, row)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert response.status_code == 200 and len(reads) == 2
    assert (user.email, profile.student_number) == identity
    assert all("email=" not in statement and "student_number=" not in statement for statement in writes)


@pytest.mark.parametrize("identity,code", [("email", "CHANGE_REQUEST_STALE"),
                                         ("student_number", "STUDENT_NUMBER_ALREADY_REGISTERED")])
def test_real_mysql_unique_failure_is_rolled_back_and_sanitized(db_session, db_client, evidence, identity, code, caplog):
    _, user, _, profile, row, _, _ = evidence
    actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
    injected = []

    def duplicate(session, _context, _instances):
        if not injected and row.status == "APPROVED":
            injected.append(True)
            if identity == "email":
                session.add(User(email=user.email, password_hash="PRIVATE-HASH", role_code="STUDENT",
                                 account_status="PENDING_VERIFICATION", first_name="PRIVATE-DB-VALUE", last_name="Duplicate"))
            else:
                session.add(StudentProfile(user_id=actor.user_id, student_number=profile.student_number,
                    campus_id=profile.campus_id, program_id=profile.program_id, year_level=1, section="PRIVATE-DB-VALUE"))

    event.listen(db_session, "before_flush", duplicate)
    try:
        response = approve(db_client, row)
    finally:
        event.remove(db_session, "before_flush", duplicate)
    assert injected == [True] and response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] == {}
    for private in ("PRIVATE-HASH", "PRIVATE-DB-VALUE", user.email, profile.student_number,
                    "uq_users_email", "uq_student_profiles_number", "INSERT INTO", "Duplicate entry"):
        assert private not in response.text + caplog.text
    assert db_session.is_active
    unchanged(db_session, evidence)


@pytest.mark.parametrize("error", [
    IntegrityError("PRIVATE-SQL", {"value": "PRIVATE-PARAM"}, MysqlIntegrityError(1062,
        "Duplicate entry 'PRIVATE-DRIVER' for key 'profile_change_requests.uq_unrelated'")),
    IntegrityError("PRIVATE-SQL", {"value": "PRIVATE-PARAM"}, MysqlIntegrityError(1452,
        "PRIVATE-DRIVER for key 'users.uq_users_email'")),
    OperationalError("PRIVATE-SQL", {"value": "PRIVATE-PARAM"}, MysqlOperationalError(1213, "PRIVATE-DEADLOCK")),
])
def test_unknown_database_failure_is_generic_not_mislabeled_or_logged(db_session, db_client, evidence, monkeypatch, error, caplog):
    row = evidence[4]
    original = db_session.flush
    injected = []

    def fail(*args, **kwargs):
        result = original(*args, **kwargs)
        if not injected and row.status == "APPROVED":
            injected.append(True)
            raise error
        return result

    monkeypatch.setattr(db_session, "flush", fail)
    response = approve(db_client, row)
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "details": {}}}
    for private in ("PRIVATE-SQL", "PRIVATE-PARAM", "PRIVATE-DRIVER", "PRIVATE-DEADLOCK", "uq_unrelated"):
        assert private not in response.text + caplog.text
    unchanged(db_session, evidence)


@pytest.mark.parametrize("identity", ["email", "student_number"])
def test_identity_query_driver_error_does_not_log_bound_identifiers(db_session, db_client, evidence, monkeypatch, caplog, identity):
    method = "find_user_by_email" if identity == "email" else "find_student_profile_by_number"

    def fail(*args, **kwargs):
        raise OperationalError("PRIVATE-LOOKUP-SQL", {"identifier": "PRIVATE-IDENTIFIER"},
                               MysqlOperationalError(2013, "PRIVATE-DRIVER"))

    monkeypatch.setattr(AccountsRepository, method, fail)
    response = approve(db_client, evidence[4])
    assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
    for private in ("PRIVATE-LOOKUP-SQL", "PRIVATE-IDENTIFIER", "PRIVATE-DRIVER"):
        assert private not in response.text + caplog.text
    unchanged(db_session, evidence)
