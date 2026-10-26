"""Strict approval input and locked version binding without side effects on denial."""

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.modules.audit.models import AuditEvent
from app.modules.profile_change.service import ProfileChangeService
from app.modules.profile_change.repository import ProfileChangeRepository
from app.modules.accounts.models import User
from .test_correction_evidence_availability import evidence  # noqa: F401


def csrf(client):
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


def assert_unchanged(db_session, values, audit_count):
    _, user, screening, profile, request, _, path = values
    db_session.refresh(request)
    db_session.refresh(user)
    db_session.refresh(profile)
    assert request.status == "PENDING"
    assert request.reviewed_by_user_id is request.reviewed_at is None
    assert user.account_status == "ACTIVE" and (user.first_name, user.last_name) == ("Juan", "Cruz")
    assert profile.section == "A" and screening.status == "PASSED" and path.exists()
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count


@pytest.mark.parametrize("body", [None, {}, {"submission_version": None}, {"submission_version": True},
    {"submission_version": "1"}, {"submission_version": 1.0}, {"submission_version": 0}, {"submission_version": -1},
    {"submission_version": []}, {"submission_version": "PRIVATE-INVALID"},
    *[{"submission_version": 1, field: "PRIVATE-OVERRIDE"} for field in
      ("student_user_id", "role_code", "reviewed_by_user_id", "status", "requested_section", "proposed_changes")]])
def test_approval_body_requires_only_strict_recorded_version(db_session, db_client, evidence, body, caplog):
    request = evidence[4]
    headers = csrf(db_client)
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve", headers=headers,
                              **({"json": body} if body is not None else {}))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "PRIVATE-INVALID" not in response.text + caplog.text
    assert "PRIVATE-OVERRIDE" not in response.text + caplog.text
    assert_unchanged(db_session, evidence, count)


def test_wrong_version_is_safe_conflict_without_changes(db_session, db_client, evidence):
    request = evidence[4]
    headers = csrf(db_client)
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve", headers=headers,
                              json={"submission_version": 2})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CHANGE_REQUEST_VERSION_CONFLICT"
    assert response.json()["error"]["details"] == {}
    assert_unchanged(db_session, evidence, count)


def test_matching_version_preserves_success_and_repeated_decision_conflict(db_session, db_client, evidence):
    request = evidence[4]
    headers = csrf(db_client)
    response = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve", headers=headers,
                              json={"submission_version": 1})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["change_request"]["status"] == "APPROVED"
    assert evidence[3].section == "B" and not evidence[-1].exists()
    repeated = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve", headers=headers,
                              json={"submission_version": 2})
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "CHANGE_REQUEST_NOT_PENDING"


def test_legacy_unknown_version_cannot_be_invented_for_approval(db_session, db_client, evidence):
    request = evidence[4]
    request.submission_version = None
    db_session.commit()
    headers = csrf(db_client)
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve", headers=headers,
                              json={"submission_version": 1})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COR_EVIDENCE_UNAVAILABLE"
    assert_unchanged(db_session, evidence, count)


def test_version_is_checked_after_current_request_lock(db_session, db_client, evidence, monkeypatch):
    request = evidence[4]
    original = ProfileChangeRepository.lock_by_id

    def newer(self, request_id):
        row = original(self, request_id)
        row.submission_version = 2
        return row

    monkeypatch.setattr(ProfileChangeRepository, "lock_by_id", newer)
    headers = csrf(db_client)
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve", headers=headers,
                              json={"submission_version": 1})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CHANGE_REQUEST_VERSION_CONFLICT"
    assert_unchanged(db_session, evidence, count)


@pytest.mark.parametrize("value", [None, True, "1", 0])
def test_service_cannot_bypass_strict_version_binding(db_session, evidence, value):
    actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    with pytest.raises(AppError) as error:
        ProfileChangeService(db_session).approve(actor, evidence[4].change_request_id, submission_version=value)
    assert error.value.code == "VALIDATION_ERROR"
    assert_unchanged(db_session, evidence, count)


@pytest.mark.parametrize("token", [None, "wrong-csrf"])
def test_approval_still_requires_session_csrf(db_session, db_client, evidence, token):
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.post(f"/api/v1/profile-change-requests/{evidence[4].change_request_id}/approve",
        json={"submission_version": 1}, headers={} if token is None else {"X-CSRF-Token": token})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
    assert_unchanged(db_session, evidence, count)
