"""Safe Users operations and independent operational deactivation enforcement."""

from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.accounts.service import AccountsService
from app.modules.auth.models import UserSession
from app.modules.auth.service import AuthService
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from .test_correction_resubmission_preflight import returned_context  # noqa: F401
from .test_correction_approval_version import csrf
from .test_student_correction_reads import login


@pytest.fixture
def users(db_session, returned_context):
    staff = [User(email=f"managed-{role}@example.edu", password_hash=hash_password("password1"),
        role_code=role, account_status="ACTIVE", first_name="Percent%_!" if role == "COUNSELOR" else "Staff",
        last_name="Managed") for role in ("COUNSELOR", "GUIDANCE_STAFF")]
    db_session.add_all(staff)
    db_session.commit()
    return returned_context, staff


def admin(client, db=None):
    login(client, "edit-super@example.edu", "super-pass-1")
    if db is not None:
        db.commit()


def status(client, target, action="deactivate", body=None):
    return client.post(f"/api/v1/accounts/users/{target.user_id}/{action}",
        headers=csrf(client), json={} if body is None else body)


def test_safe_sql_paged_search_and_detail(db_client, db_session, users):
    context, staff = users
    student = context[1]
    db_session.add(User(email="unrelated-page@example.edu", password_hash="not-a-login-credential",
                        role_code="STUDENT", account_status="PENDING_VERIFICATION",
                        first_name="Unrelated", last_name="Pagination"))
    db_session.commit()
    admin(db_client, db_session)
    expected_ids = set(db_session.scalars(select(User.user_id)))
    listing = db_client.get("/api/v1/accounts/users", params={"page_size": 2})
    assert listing.status_code == 200 and listing.json()["total"] == len(expected_ids)
    assert listing.headers["cache-control"] == "no-store"
    assert db_client.get("/api/v1/accounts/users", params={"q": " " * 330 + "Dela" + " " * 330}).json()["total"] == 1
    # Independent-connection/live suites commit synthetic rows in the shared
    # disposable schema; verify every actual ID rather than assuming emptiness.
    pages = [db_client.get("/api/v1/accounts/users", params={"page_size": 2, "page": page}).json()["items"]
             for page in range(1, (len(expected_ids) + 1) // 2 + 1)]
    actual_ids = [item["user_id"] for items in pages for item in items]
    assert len(actual_ids) == len(expected_ids) and set(actual_ids) == expected_ids
    assert len(db_client.get("/api/v1/accounts/users", params={"q": "%_!"}).json()["items"]) == 1
    assert db_client.get("/api/v1/accounts/users", params={"q": "Dela"}).json()["items"][0]["user_id"] == student.user_id
    assert db_client.get("/api/v1/accounts/users", params={"q": context[3].student_number}).json()["total"] == 1
    assert db_client.get("/api/v1/accounts/users", params={"role_code": "GUIDANCE_STAFF"}).json()["total"] == 1
    detail = db_client.get(f"/api/v1/accounts/users/{student.user_id}")
    assert detail.json()["profile"]["section"] == "A" and detail.json()["valid_until"]
    for secret in ("password", "token", "session_id", "storage_key", "requested_section", "clinical"):
        assert secret not in detail.text and secret not in listing.text
    assert db_client.get("/api/v1/accounts/users/99999999").status_code == 404


def test_deactivate_revokes_all_sessions_idempotently_and_reactivate_needs_new_login(db_client, db_session, users):
    context, _ = users
    _, student, enrolled, profile, old, _, _ = context
    _user, session, raw, _csrf = AuthService(db_session).login(student.email, "password1")
    db_session.commit()
    original = student.account_status, enrolled.valid_until, enrolled.confirmed_at, profile.section, old.status
    admin(db_client, db_session)
    result = status(db_client, student)
    assert result.status_code == 200 and result.json()["is_deactivated"] is True
    db_session.refresh(session)
    assert session.revocation_reason == "ACCOUNT_DISABLED"
    assert not db_session.scalar(select(func.count()).select_from(UserSession).where(
        UserSession.user_id == student.user_id, UserSession.revoked_at.is_(None)))
    assert status(db_client, student).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "account_deactivated")) == 1
    with pytest.raises(AppError):
        AuthService(db_session).authenticate_request(raw, None, is_safe_method=True)
    denied = db_client.post("/api/v1/auth/login", json={"identifier": student.email, "password": "password1"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"
    assert status(db_client, student, "reactivate").status_code == 200
    assert status(db_client, student, "reactivate").status_code == 200
    with pytest.raises(AppError):
        AuthService(db_session).authenticate_request(raw, None, is_safe_method=True)
    assert original[:2] == (student.account_status, enrolled.valid_until)
    assert (profile.section, old.status) == original[3:]
    login(db_client, student.email)
    assert db_client.get("/api/v1/auth/me").json()["is_deactivated"] is False


@pytest.mark.parametrize("role", ["STUDENT", "COUNSELOR", "GUIDANCE_STAFF"])
def test_non_superadmin_cannot_manage(db_client, users, role):
    context, staff = users
    actor = context[1] if role == "STUDENT" else next(user for user in staff if user.role_code == role)
    login(db_client, actor.email)
    assert db_client.get("/api/v1/accounts/users").status_code == 403
    assert status(db_client, context[1]).status_code == 403


def test_protected_targets_strict_body_csrf_and_pending_status(db_client, db_session, users):
    context, staff = users
    admin(db_client, db_session)
    reviewer = AccountsService(db_session).repository.find_user_by_email("edit-super@example.edu")
    for target in (reviewer, staff[1]):
        denied = status(db_client, target)
        assert denied.json()["error"]["code"] == "USER_STATUS_CHANGE_FORBIDDEN"
        assert denied.headers["cache-control"] == "no-store"
    invalid = status(db_client, context[1], body={"account_status": "ACTIVE"})
    assert invalid.status_code == 422 and invalid.headers["cache-control"] == "no-store"
    assert db_client.post(f"/api/v1/accounts/users/{context[1].user_id}/deactivate", json={}).status_code == 403
    context[1].account_status = "VERIFICATION_EXPIRED"
    db_session.commit()
    assert status(db_client, context[1]).status_code == 200
    assert status(db_client, context[1], "reactivate").json()["account_status"] == "VERIFICATION_EXPIRED"


def test_failed_audit_rolls_back_flag_and_revocation(db_session, users, monkeypatch):
    context, _ = users
    student = context[1]
    reviewer = AccountsService(db_session).repository.find_user_by_email("edit-super@example.edu")
    _, session, _, _ = AuthService(db_session).login(student.email, "password1")
    db_session.commit()
    def fail(*args, **kwargs):
        raise RuntimeError("Injected audit failure")
    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError):
        AccountsService(db_session).change_user_status(reviewer, student.user_id, deactivated=True)
    db_session.refresh(student)
    db_session.refresh(session)
    assert student.is_deactivated is False and session.revoked_at is None


def test_anonymous_token_is_not_user_management_authority(db_client, users):
    result = db_client.get("/api/v1/accounts/users", headers={"X-COR-Token": "opaque"})
    assert result.status_code == 401 and result.headers["cache-control"] == "no-store"


def test_disabled_counselors_are_not_offered_for_booking(db_session, users):
    from app.modules.appointments.repository import AppointmentsRepository
    context, staff = users
    counselor = staff[0]
    repository = AppointmentsRepository(db_session)
    assert counselor.user_id in repository.active_counselor_ids()
    manager = AccountsService(db_session)
    manager.change_user_status(manager.repository.find_user_by_email("edit-super@example.edu"), counselor.user_id, deactivated=True)
    assert counselor.user_id not in repository.active_counselor_ids()
    assert counselor.user_id not in [user.user_id for user in repository.active_counselors()]


def test_cor_token_and_recovery_do_not_bypass_deactivation(db_session, users):
    from app.modules.cor_screening.service import CorScreeningService
    context, _ = users
    service, student, enrolled, _, _, _, _ = context
    student.account_status = "PENDING_VERIFICATION"
    enrolled.status = "AWAITING_CONFIRMATION"
    raw = service._issue_verification_token(enrolled, datetime.now(timezone.utc))
    student.is_deactivated = True
    db_session.commit()
    with pytest.raises(AppError):
        service.resolve_verification_token(raw)
    manager = AccountsService(db_session).repository.find_user_by_email("edit-super@example.edu")
    with pytest.raises(AppError) as caught:
        service.recover_student(manager, student.user_id)
    assert caught.value.code == "ACCOUNT_DEACTIVATED"
    assert student.is_deactivated is True and enrolled.status == "AWAITING_CONFIRMATION"


def test_database_failure_is_sanitized_and_atomic(db_session, users, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from pymysql.err import OperationalError as MysqlOperationalError
    context, _ = users
    service = AccountsService(db_session)
    manager = service.repository.find_user_by_email("edit-super@example.edu")
    def fail(*args, **kwargs):
        raise OperationalError("PRIVATE SQL", {}, MysqlOperationalError(1213, "PRIVATE DRIVER"))
    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(AppError) as caught:
        service.change_user_status(manager, context[1].user_id, deactivated=True)
    assert caught.value.code == "INTERNAL_ERROR" and "PRIVATE" not in caught.value.message
    db_session.refresh(context[1])
    assert context[1].is_deactivated is False


@pytest.mark.parametrize("query", [{"role_code": "ADMIN"}, {"account_status": "DISABLED"},
    {"is_deactivated": "invalid"}, {"page": 0}, {"page_size": 101}, {"q": "x" * 321}])
def test_invalid_list_filters_are_safe_and_private(db_client, db_session, users, query):
    admin(db_client, db_session)
    result = db_client.get("/api/v1/accounts/users", params=query)
    assert result.status_code == 422 and result.headers["cache-control"] == "no-store"
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_manager_authorization_is_rechecked_under_lock(db_session, users):
    context, _ = users
    service = AccountsService(db_session)
    manager = service.repository.find_user_by_email("edit-super@example.edu")
    cached = SimpleNamespace(user_id=manager.user_id, role_code="SUPERADMIN", account_status="ACTIVE", is_deactivated=False)
    manager.is_deactivated = True
    db_session.commit()
    with pytest.raises(AppError) as caught:
        service.change_user_status(cached, context[1].user_id, deactivated=True)
    assert caught.value.code == "FORBIDDEN_ROLE"
    assert context[1].is_deactivated is False


def test_validation_does_not_echo_untrusted_field_names(db_client, db_session, users):
    admin(db_client, db_session)
    result = status(db_client, users[0][1], body={"PRIVATE-KEY": "PRIVATE-VALUE"})
    assert result.status_code == 422 and result.headers["cache-control"] == "no-store"
    assert "PRIVATE" not in result.text
