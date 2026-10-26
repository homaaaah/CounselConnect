"""Superadmin Counselor provisioning/editing on isolated MySQL only."""

from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.modules.accounts.models import StudentProfile, User
from app.modules.accounts.schemas import CounselorAccountCreateRequest
from app.modules.accounts.service import AccountsService
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.auth.models import UserSession
from app.modules.auth.service import AuthService
from .test_student_correction_reads import login


@pytest.fixture
def accounts(db_session, db_client):
    result = {}
    password_hash = hash_password("existing-test-password")
    for role in ("SUPERADMIN", "COUNSELOR", "GUIDANCE_STAFF", "STUDENT"):
        row = User(email=f"counselor-manager-{role.lower()}@example.edu", password_hash=password_hash,
                   role_code=role, account_status="ACTIVE", first_name="Existing", last_name=role)
        db_session.add(row)
        result[role] = row
    db_session.commit()
    auth = login(db_client, result["SUPERADMIN"].email, "existing-test-password")
    return result, {"X-CSRF-Token": auth["csrf_token"]}


def payload(**updates):
    return {"first_name": "  Ana\t Maria ", "middle_name": " ", "last_name": " Santos ",
            "email": "new-counselor@example.edu", "password": "initial-test-password", **updates}


def edit_payload(client, target, **updates):
    response = client.get(f"/api/v1/accounts/users/{target.user_id}")
    assert response.status_code == 200
    data = response.json()
    return {key: data[key] for key in ("email", "first_name", "middle_name", "last_name")} | {
        "expected_updated_at": data["updated_at"], **updates}


def test_create_safe_account_hash_audit_and_staff_login(db_session, db_client, accounts, caplog):
    _, headers = accounts
    response = db_client.post("/api/v1/accounts/users", json=payload(), headers=headers)
    assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
    data = response.json()
    assert (data["role_code"], data["account_status"], data["is_deactivated"]) == ("COUNSELOR", "ACTIVE", False)
    assert (data["first_name"], data["middle_name"], data["last_name"]) == ("Ana Maria", None, "Santos")
    assert data["profile"] is None and data["student_number"] is None
    assert data["updated_at"].endswith("Z")
    row = db_session.get(User, data["user_id"])
    assert row.password_hash.startswith("$argon2id$") and verify_password("initial-test-password", row.password_hash)
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.event_type == "counselor_account_created"))
    assert event.target_id == row.user_id and event.metadata_json == {"role_code": "COUNSELOR", "account_status": "ACTIVE"}
    for value in ("initial-test-password", row.password_hash):
        assert value not in response.text and value not in str(event.metadata_json) and value not in caplog.text
    auth = login(db_client, row.email, "initial-test-password")
    assert auth["user"]["role_code"] == "COUNSELOR"


def test_edit_email_revokes_sessions_preserves_identity_password_status(db_session, db_client, accounts):
    rows, headers = accounts
    target = rows["COUNSELOR"]
    original_hash = target.password_hash
    _, session, credential, _ = AuthService(db_session).login(target.email, "existing-test-password")
    db_session.commit()
    body = edit_payload(db_client, target, email="changed-counselor@example.edu", first_name="Updated")
    response = db_client.patch(f"/api/v1/accounts/users/{target.user_id}", json=body, headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    db_session.refresh(target); db_session.refresh(session)
    assert target.email == "changed-counselor@example.edu" and target.first_name == "Updated"
    assert target.password_hash == original_hash and target.role_code == "COUNSELOR"
    assert target.account_status == "ACTIVE" and not target.is_deactivated
    assert session.revocation_reason == "ACCOUNT_UPDATED"
    with pytest.raises(AppError):
        AuthService(db_session).authenticate_request(credential, None, is_safe_method=True)
    assert db_client.post("/api/v1/auth/login", json={"identifier": body["email"].replace("changed-", ""), "password": "existing-test-password"}).status_code == 401
    assert login(db_client, target.email, "existing-test-password")["user"]["user_id"] == target.user_id
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.event_type == "counselor_account_updated"))
    assert event.metadata_json == {"changed_fields": ["email", "first_name"], "sessions_revoked": True}
    assert "changed-counselor@example.edu" not in str(event.metadata_json)


def test_name_edit_preserves_sessions_and_deactivation_and_stale_or_noop_behavior(db_session, db_client, accounts):
    rows, headers = accounts
    target = rows["COUNSELOR"]
    _, session, _, _ = AuthService(db_session).login(target.email, "existing-test-password")
    target.is_deactivated = True
    db_session.commit()
    body = edit_payload(db_client, target, middle_name="  Dela   Cruz ")
    url = f"/api/v1/accounts/users/{target.user_id}"
    response = db_client.patch(url, json=body, headers=headers)
    assert response.status_code == 200
    db_session.refresh(target); db_session.refresh(session)
    assert target.is_deactivated and target.middle_name == "Dela Cruz" and session.revoked_at is None
    assert db_client.patch(url, json=body, headers=headers).json()["error"]["code"] == "USER_EDIT_CONFLICT"
    noop = edit_payload(db_client, target)
    assert db_client.patch(url, json=noop, headers=headers).json()["updated_at"] == noop["expected_updated_at"]
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "counselor_account_updated")) == 1


@pytest.mark.parametrize("role", ["STUDENT", "COUNSELOR", "GUIDANCE_STAFF"])
@pytest.mark.parametrize("method", ["create", "edit"])
def test_other_roles_denied(db_session, db_client, accounts, role, method):
    rows, _ = accounts
    body = edit_payload(db_client, rows["COUNSELOR"], first_name="Denied") if method == "edit" else payload()
    auth = login(db_client, rows[role].email, "existing-test-password")
    headers = {"X-CSRF-Token": auth["csrf_token"]}
    response = (db_client.post("/api/v1/accounts/users", json=body, headers=headers) if method == "create" else
                db_client.patch(f"/api/v1/accounts/users/{rows['COUNSELOR'].user_id}", json=body, headers=headers))
    assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
    assert db_session.scalar(select(User).where(User.email == "new-counselor@example.edu")) is None


@pytest.mark.parametrize("role", ["STUDENT", "GUIDANCE_STAFF", "SUPERADMIN"])
def test_non_counselor_targets_are_protected(db_client, accounts, role):
    rows, headers = accounts
    body = edit_payload(db_client, rows[role], first_name="Denied")
    response = db_client.patch(f"/api/v1/accounts/users/{rows[role].user_id}", json=body, headers=headers)
    assert response.status_code == 403 and response.json()["error"]["code"] == "COUNSELOR_EDIT_FORBIDDEN"


@pytest.mark.parametrize("override", [
    {"role_code": "SUPERADMIN"}, {"is_deactivated": True}, {"account_status": "ACTIVE"},
    {"first_name": "   "}, {"first_name": 1}, {"last_name": None}, {"middle_name": ["private"]},
    {"password": "short"}, {"password": "x" * 129}, {"email": "invalid"}, {"user_id": 900},
])
def test_strict_creation_validation_and_private_errors(db_session, db_client, accounts, override):
    _, headers = accounts
    response = db_client.post("/api/v1/accounts/users", json=payload(**override), headers=headers)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert "initial-test-password" not in response.text and "new-counselor@example.edu" not in response.text
    assert db_session.scalar(select(User).where(User.email == "new-counselor@example.edu")) is None


@pytest.mark.parametrize("override", [{"role_code": "STUDENT"}, {"password": "forbidden-password"},
    {"expected_updated_at": None}, {"expected_updated_at": "2026-10-26T00:00:00"}, {"expected_updated_at": "invalid"}, {"expected_updated_at": 123456}])
def test_strict_edit_validation(db_client, accounts, override):
    rows, headers = accounts
    response = db_client.patch(f"/api/v1/accounts/users/{rows['COUNSELOR'].user_id}",
        json=edit_payload(db_client, rows["COUNSELOR"], **override), headers=headers)
    assert response.status_code == 422 and "forbidden-password" not in response.text


def test_sessions_csrf_duplicates_and_missing_targets(db_session, db_client, accounts):
    rows, headers = accounts
    assert db_client.post("/api/v1/accounts/users", json=payload()).status_code == 403
    assert db_client.post("/api/v1/accounts/users", json=payload(email=rows["STUDENT"].email), headers=headers).status_code == 409
    body = edit_payload(db_client, rows["COUNSELOR"], email=rows["STUDENT"].email)
    assert db_client.patch(f"/api/v1/accounts/users/{rows['COUNSELOR'].user_id}", json=body, headers=headers).status_code == 409
    assert db_client.patch("/api/v1/accounts/users/99999999", json=body, headers=headers).status_code == 404
    db_client.cookies.clear()
    assert db_client.post("/api/v1/accounts/users", json=payload(), headers=headers).status_code == 401


@pytest.mark.parametrize("operation", ["create", "edit"])
def test_audit_failure_rolls_back_user_and_sessions(db_session, db_client, accounts, monkeypatch, operation):
    rows, headers = accounts
    target = rows["COUNSELOR"]
    _, session, _, _ = AuthService(db_session).login(target.email, "existing-test-password")
    db_session.commit()
    original_email = target.email
    body = edit_payload(db_client, target, email="rollback-counselor@example.edu")
    def fail(*args, **kwargs):
        raise RuntimeError("Injected audit failure")
    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError, match="Injected audit failure"):
        if operation == "create":
            db_client.post("/api/v1/accounts/users", json=payload(), headers=headers)
        else:
            db_client.patch(f"/api/v1/accounts/users/{target.user_id}", json=body, headers=headers)
    db_session.refresh(target); db_session.refresh(session)
    assert target.email == original_email and session.revoked_at is None
    assert db_session.scalar(select(User).where(User.email == "new-counselor@example.edu")) is None


def test_duplicate_key_race_is_sanitized(db_client, accounts, monkeypatch):
    rows, headers = accounts
    monkeypatch.setattr(AccountsService, "_require_available_counselor_email", lambda *args, **kwargs: None)
    response = db_client.post("/api/v1/accounts/users", json=payload(email=rows["COUNSELOR"].email), headers=headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"
    for private in (rows["COUNSELOR"].email, "password_hash", "INSERT", "uq_users_email"):
        assert private not in response.text


def test_stale_actor_is_rechecked_under_lock(db_session, accounts):
    rows, _ = accounts
    actor = rows["SUPERADMIN"]
    stale = SimpleNamespace(user_id=actor.user_id, role_code="SUPERADMIN", account_status="ACTIVE", is_deactivated=False)
    actor.is_deactivated = True
    db_session.commit()
    with pytest.raises(AppError) as error:
        AccountsService(db_session).create_counselor(stale, CounselorAccountCreateRequest(**payload()))
    assert error.value.status_code == 403


def test_email_cannot_shadow_student_number(db_session, db_client, accounts, academic_references):
    rows, headers = accounts
    campus, program = academic_references
    db_session.add(StudentProfile(user_id=rows["STUDENT"].user_id, student_number="number-as-email@example.edu",
        campus_id=campus, program_id=program, year_level=1, section="A"))
    db_session.commit()
    response = db_client.post("/api/v1/accounts/users", json=payload(email="number-as-email@example.edu"), headers=headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "ACCOUNT_IDENTIFIER_CONFLICT"
