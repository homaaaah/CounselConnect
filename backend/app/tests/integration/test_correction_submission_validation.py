"""Submission whitelist and real token/session authorization boundaries."""

import pytest
from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.models import ProfileChangeRequest
from .test_profile_change import _payload, good_result, stub_screening


@pytest.fixture
def submission(db_session, academic_references, monkeypatch):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, token = service.register_with_cor(
        "whitelist@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    return user, screening, token, _payload(*academic_references).model_dump()


def login(client):
    response = client.post("/api/v1/auth/login", json={
        "identifier": "whitelist@example.edu", "password": "password1",
    })
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def unchanged(db_session, user, screening, token_hash, audit_count):
    db_session.refresh(user)
    db_session.refresh(screening)
    assert user.account_status == "PENDING_VERIFICATION"
    assert (user.first_name, user.last_name) == ("Juan", "Cruz")
    assert screening.status == "AWAITING_CONFIRMATION"
    assert screening.verification_token_hash == token_hash
    assert db_session.scalar(select(func.count()).select_from(ProfileChangeRequest)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
@pytest.mark.parametrize("auth", ["token", "session"])
@pytest.mark.parametrize("extra", [
    "student_user_id", "user_id", "cor_screening_id", "role_code",
    "reviewed_by_user_id", "status", "account_status", "is_deactivated",
    "submission_version", "evidence_file_id", "unsupported_field",
])
def test_extra_fields_rejected_without_values_or_side_effects(
    db_client, db_session, submission, action, auth, extra, caplog,
):
    user, screening, token, payload = submission
    headers = {"X-COR-Token": token} if auth == "token" else login(db_client)
    audit_count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    token_hash = screening.verification_token_hash
    payload[extra] = {"secret": "PRIVATE-SUBMITTED-VALUE"}
    response = db_client.post(f"/api/v1/cor-screenings/{action}", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json() == {"error": {
        "code": "VALIDATION_ERROR", "message": "Request validation failed.",
        "details": {"fields": [{"loc": ["body", extra], "type": "extra_forbidden",
                                  "message": "Invalid or missing value."}]},
    }}
    assert "PRIVATE-SUBMITTED-VALUE" not in response.text + caplog.text
    assert token not in response.text + caplog.text
    unchanged(db_session, user, screening, token_hash, audit_count)


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
@pytest.mark.parametrize("csrf", [None, "wrong-csrf"])
def test_session_submission_requires_csrf(db_client, db_session, submission, action, csrf):
    user, screening, _, payload = submission
    login(db_client)
    token_hash = screening.verification_token_hash
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.post(f"/api/v1/cor-screenings/{action}", json=payload,
        headers={} if csrf is None else {"X-CSRF-Token": csrf})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
    unchanged(db_session, user, screening, token_hash, count)


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
def test_invalid_token_never_falls_back_to_session(db_client, submission, action):
    _, _, _, payload = submission
    headers = login(db_client)
    headers["X-COR-Token"] = "PRIVATE-INVALID-TOKEN"
    response = db_client.post(f"/api/v1/cor-screenings/{action}", json=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"
    assert "PRIVATE-INVALID-TOKEN" not in response.text


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
@pytest.mark.parametrize("auth", ["token", "session"])
def test_other_identity_cannot_be_submitted(db_client, db_session, submission, action, auth):
    user, screening, token, payload = submission
    headers = {"X-COR-Token": token} if auth == "token" else login(db_client)
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    token_hash = screening.verification_token_hash
    payload["student_number"] = "20239999-B"
    response = db_client.post(f"/api/v1/cor-screenings/{action}", json=payload, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "STUDENT_NUMBER_MISMATCH"
    assert "20239999-B" not in response.text
    unchanged(db_session, user, screening, token_hash, count)


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
def test_anonymous_submission_is_denied(db_client, submission, action):
    _, _, _, payload = submission
    response = db_client.post(f"/api/v1/cor-screenings/{action}", json=payload)
    assert response.status_code == 401


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
@pytest.mark.parametrize("auth", ["token", "session"])
def test_invalid_supported_value_is_not_echoed(db_client, submission, action, auth, caplog):
    _, _, token, payload = submission
    headers = {"X-COR-Token": token} if auth == "token" else login(db_client)
    payload["year_level"] = "PRIVATE-INVALID-YEAR"
    response = db_client.post(f"/api/v1/cor-screenings/{action}", json=payload, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "PRIVATE-INVALID-YEAR" not in response.text + caplog.text


@pytest.mark.parametrize("action", ["confirm", "request-edit"])
@pytest.mark.parametrize("auth", ["token", "session"])
def test_supported_body_still_activates_only_authenticated_owner(
    db_client, db_session, submission, monkeypatch, action, auth,
):
    user, screening, token, payload = submission
    stub_screening(monkeypatch, good_result(student_no="20239999-B"))
    other, other_screening, _, _, _ = CorScreeningService(db_session).register_with_cor(
        "other-whitelist@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    headers = {"X-COR-Token": token} if auth == "token" else login(db_client)
    payload["first_name"] = "  JUAN  "
    if action == "request-edit":
        payload["section"] = "  B  "
    response = db_client.post(f"/api/v1/cor-screenings/{action}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["user_id"] == user.user_id
    assert data["user"]["account_status"] == "ACTIVE"
    assert data["user"]["first_name"] == "Juan"
    assert data["screening"]["cor_screening_id"] == screening.cor_screening_id
    if action == "request-edit":
        assert data["change_request"]["student_user_id"] == user.user_id
        assert data["change_request"]["requested_section"] == "B"
        assert data["profile"]["section"] == "A"
    db_session.refresh(other)
    db_session.refresh(other_screening)
    assert other.account_status == "PENDING_VERIFICATION"
    assert other_screening.status == "AWAITING_CONFIRMATION"
