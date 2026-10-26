"""Legacy reject is the exact version-bound return compatibility operation."""

import pytest
from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf
from .test_correction_manual_return import pending_unchanged


def alias(client, row, body):
    return client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/reject",
                       headers=csrf(client), json=body)


@pytest.mark.parametrize("legacy", [False, True])
def test_alias_returns_same_safe_detail_and_new_returned_decision(db_session, db_client, evidence, legacy):
    _, user, _, profile, row, _, path = evidence
    if legacy:
        row.submission_version = None
        row.registered_values_json = row.extracted_values_json = None
        db_session.commit()
    response = alias(db_client, row, {"submission_version": None if legacy else 1, "reason": "  Check the section.\n "})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["change_request"]["status"] == "RETURNED"
    assert body["change_request"]["submission_version"] == (None if legacy else 1)
    assert body["change_request"]["decision_reason"] == "Check the section."
    assert body["evidence"]["availability"] == "RESOLVED" and not path.exists()
    assert user.account_status == "ACTIVE" and profile.section == "A"
    assert db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}").json() == body
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "profile_change_returned", AuditEvent.target_id == row.change_request_id)) == 1
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "profile_change_rejected", AuditEvent.target_id == row.change_request_id)) == 0
    canonical = db_client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/return", headers=csrf(db_client),
        json={"submission_version": None if legacy else 1, "reason": "Cannot replay"})
    assert canonical.status_code == 409 and canonical.json()["error"]["code"] == "CHANGE_REQUEST_NOT_PENDING"


@pytest.mark.parametrize("body,code,status", [
    ({"reason": "Fix it"}, "VALIDATION_ERROR", 422),
    ({"submission_version": True, "reason": "Fix it"}, "VALIDATION_ERROR", 422),
    ({"submission_version": "1", "reason": "Fix it"}, "VALIDATION_ERROR", 422),
    ({"submission_version": 0, "reason": "Fix it"}, "VALIDATION_ERROR", 422),
    ({"submission_version": 1, "reason": " \t "}, "CHANGE_REQUEST_REASON_REQUIRED", 422),
    ({"submission_version": 1, "reason": "x" * 501}, "VALIDATION_ERROR", 422),
    ({"submission_version": 1, "reason": "Fix it", "student_user_id": "PRIVATE-OVERRIDE"}, "VALIDATION_ERROR", 422),
    ({"submission_version": 2, "reason": "Fix it"}, "CHANGE_REQUEST_VERSION_CONFLICT", 409),
    ({"submission_version": None, "reason": "Fix it"}, "CHANGE_REQUEST_VERSION_CONFLICT", 409),
])
def test_alias_uses_identical_strict_input_and_version_rules(db_session, db_client, evidence, body, code, status, caplog):
    response = alias(db_client, evidence[4], body)
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert "PRIVATE-OVERRIDE" not in response.text + caplog.text
    pending_unchanged(db_session, evidence)


def test_alias_does_not_relabel_a_historical_rejected_row(db_session, db_client, evidence):
    row = evidence[4]
    row.status, row.decision_reason = "REJECTED", "Historical decision"
    db_session.commit()
    response = alias(db_client, row, {"submission_version": 1, "reason": "New reason"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "CHANGE_REQUEST_NOT_PENDING"
    db_session.refresh(row)
    assert (row.status, row.decision_reason) == ("REJECTED", "Historical decision")


def test_alias_requires_session_csrf(db_session, db_client, evidence):
    row = evidence[4]
    body = {"submission_version": 1, "reason": "Fix it"}
    response = db_client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/reject", json=body)
    assert response.status_code == 403 and response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
    db_client.cookies.clear()
    response = db_client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/reject", json=body,
                              headers={"X-COR-Token": "not-a-session"})
    assert response.status_code == 401
    pending_unchanged(db_session, evidence)
