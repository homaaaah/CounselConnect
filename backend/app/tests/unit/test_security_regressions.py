"""Regression checks that never require a database or real private files."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import sha256_digest, session_csrf_token
from app.database import get_session
from app.modules.auth.service import AuthService
from app.modules.enrollment_verification.service import EnrollmentVerificationService


def registration_payload():
    return {
        "email": "test@example.edu",
        "password": "test-password-1",
        "first_name": "Ana",
        "last_name": "Santos",
        "student_number": "2026-001",
        "campus_id": 1,
        "program_id": 1,
        "year_level": 1,
        "section": "A",
    }


def test_validation_errors_never_echo_password_or_body(client):
    secret = "synthetic-secret-not-for-error-responses"
    response = client.post("/api/v1/auth/login", json={"password": secret})
    assert response.status_code == 422
    assert secret not in response.text
    details = response.json()["error"]["details"]
    assert isinstance(details, dict)
    assert details["fields"][0]["loc"] == ["body", "identifier"]
    assert all(set(field) == {"loc", "type", "message"} for field in details["fields"])


@pytest.mark.parametrize(
    "field,limit",
    [
        ("first_name", 100),
        ("middle_name", 100),
        ("last_name", 100),
        ("student_number", 50),
        ("section", 50),
    ],
)
def test_json_and_multipart_share_registration_limits(client, field, limit):
    data = {**registration_payload(), field: "x" * (limit + 1)}
    json_response = client.post("/api/v1/accounts/register/student", json=data)
    form_response = client.post(
        "/api/v1/accounts/register/student-with-cor",
        data=data,
        files={"file": ("cor.pdf", b"%PDF-test", "application/pdf")},
    )
    for response in (json_response, form_response):
        assert response.status_code == 422
        assert data["password"] not in response.text
        assert response.json()["error"]["details"]["fields"][0]["loc"] == [
            "body",
            field,
        ]


def test_plain_client_has_no_application_database(app):
    assert get_session in app.dependency_overrides
    with next(app.dependency_overrides[get_session]()) as session:
        assert session.bind is None


def test_application_engine_is_forbidden_during_tests():
    from app import database

    with pytest.raises(AssertionError, match="application database is forbidden"):
        database.get_engine()


def test_database_test_url_never_falls_back_to_application_settings(monkeypatch):
    from app.tests.conftest import _test_url

    monkeypatch.delenv("COUNSELCONNECT_TEST_DATABASE_URL", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _test_url()
    monkeypatch.setenv(
        "COUNSELCONNECT_TEST_DATABASE_URL",
        "mysql+pymysql://test@localhost/counselconnect",
    )
    with pytest.raises(pytest.fail.Exception):
        _test_url()


def test_openapi_declares_sanitized_validation_errors(app):
    schema = app.openapi()
    response = schema["paths"]["/api/v1/auth/login"]["post"]["responses"]["422"]
    alternatives = response["content"]["application/json"]["schema"]["anyOf"]
    assert {item["$ref"].rsplit("/", 1)[-1] for item in alternatives} == {"ValidationErrorResponse", "ErrorResponse"}
    assert set(
        schema["components"]["schemas"]["ValidationFieldError"]["properties"]
    ) == {"loc", "type", "message"}


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_STAFF"])
def test_student_number_cannot_shadow_staff_email(role):
    service = AuthService(Session())
    staff = SimpleNamespace(user_id=1, role_code=role)
    service.accounts = Mock()
    service.accounts.find_user_by_email.return_value = staff
    service.accounts.find_student_profile_by_number.return_value = SimpleNamespace(
        user_id=2
    )
    assert service._find_user_by_identifier("staff@example.edu") is staff
    service.accounts.find_student_profile_by_number.assert_not_called()


def test_student_email_is_not_a_staff_login():
    service = AuthService(Session())
    service.accounts = Mock()
    service.accounts.find_user_by_email.return_value = SimpleNamespace(
        role_code="STUDENT"
    )
    service.accounts.find_student_profile_by_number.return_value = None
    assert service._find_user_by_identifier("student@example.edu") is None


def test_unknown_identifier_verifies_once_without_hashing_again(monkeypatch):
    from app.modules.auth import service as module

    service = AuthService(Session())
    service._find_user_by_identifier = Mock(return_value=None)
    verify, hashing = Mock(return_value=False), Mock()
    monkeypatch.setattr(module, "verify_password", verify)
    monkeypatch.setattr(module, "hash_password", hashing)
    with pytest.raises(AppError):
        service.login("unknown", "synthetic-password")
    verify.assert_called_once_with("synthetic-password", module.DUMMY_PASSWORD_HASH)
    hashing.assert_not_called()


def test_csrf_recovery_is_stable_across_tabs_and_digest_only():
    service = AuthService(Session())
    row = SimpleNamespace(
        csrf_token_hash=sha256_digest(session_csrf_token("credential"))
    )
    first = service.recover_csrf_token(row, "credential")
    second = service.recover_csrf_token(row, "credential")
    assert first == second
    assert row.csrf_token_hash == sha256_digest(first)
    assert first != "credential"
    assert first != session_csrf_token("other-credential")


def test_session_recovery_does_not_renew_idle_activity():
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        revoked_at=None,
        last_activity_at=now - timedelta(minutes=20),
        absolute_expires_at=now + timedelta(hours=10),
        user_id=1,
        session_id=1,
    )
    service = AuthService(Session())
    service.repository = Mock()
    service.repository.find_session_by_token_hash.return_value = row
    service.accounts = Mock()
    service.accounts.get.return_value = SimpleNamespace(account_status="ACTIVE")
    service.authenticate_request(
        "credential", None, is_safe_method=True, record_activity=False
    )
    service.repository.touch_session.assert_not_called()


def test_failed_cor_deletion_keeps_retry_metadata(monkeypatch):
    service = EnrollmentVerificationService(Session())
    service.repository = Mock()
    service._lock_verification = Mock(return_value=SimpleNamespace(status="APPROVED"))
    row = SimpleNamespace(
        file_id=1, storage_key="cor/test.pdf", cleanup_state="PENDING"
    )
    service.repository.list_files_for_verification.return_value = [row]
    monkeypatch.setattr(service, "_delete_cor_bytes", lambda _: False)
    service._purge_cor_files(1)
    assert row.cleanup_state == "FAILED"
    service.repository.session.delete.assert_not_called()
    monkeypatch.setattr(service, "_delete_cor_bytes", lambda _: True)
    service._purge_cor_files(1)
    service.repository.session.delete.assert_called_once_with(row)


def test_expired_cor_is_denied_before_read_or_decision(monkeypatch):
    service = EnrollmentVerificationService(Session())
    service.repository = Mock()
    verification = SimpleNamespace(
        verification_id=1,
        status="PENDING",
        submitted_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    monkeypatch.setattr(service, "_purge_cor_files", Mock())
    with pytest.raises(AppError) as caught:
        service._require_current_cor(verification)
    assert caught.value.code == "VERIFICATION_EXPIRED"
    assert verification.status == "EXPIRED"
    service.repository.session.commit.assert_called_once()
    service._purge_cor_files.assert_called_once_with(1)


def test_private_storage_rejects_path_escape(tmp_path):
    service = EnrollmentVerificationService(Session())
    outside = tmp_path / "keep.pdf"
    outside.write_bytes(b"private-test")
    assert service._delete_cor_bytes(str(outside)) is False
    assert outside.read_bytes() == b"private-test"


def test_abandoned_upload_marker_is_reconciled_after_ttl(monkeypatch):
    import os

    service = EnrollmentVerificationService(Session())
    service.repository = Mock()
    service.repository.find_file_by_storage_key.return_value = None
    key = service._store_cor_bytes(b"%PDF-test", 1)
    path = service._storage_path(key)
    marker = path.with_suffix(".pending")
    assert marker.exists()
    # In-flight uploads must survive a concurrent cleanup pass.
    service._cleanup_abandoned_uploads(datetime.now(timezone.utc))
    assert path.exists()
    old = (datetime.now(timezone.utc) - timedelta(days=8)).timestamp()
    os.utime(marker, (old, old))
    service._cleanup_abandoned_uploads(datetime.now(timezone.utc))
    assert not path.exists() and not marker.exists()


def test_cleanup_worker_retries_without_logging_sensitive_errors(monkeypatch, caplog):
    from app.modules.enrollment_verification import cleanup

    run = Mock(side_effect=[RuntimeError("sensitive-path"), None])
    stop = Mock()
    stop.is_set.return_value = False
    stop.wait.side_effect = [False, True]
    monkeypatch.setattr(cleanup, "run_cleanup_once", run)
    cleanup.cleanup_loop(stop)
    assert run.call_count == 2
    assert "sensitive-path" not in caplog.text
    assert "verification_cleanup_worker_failed" in caplog.text
