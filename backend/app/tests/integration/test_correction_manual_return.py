"""Version-bound whole-request return without requiring available evidence."""

from datetime import datetime, timedelta, timezone

import pytest
from pymysql.err import OperationalError as MysqlOperationalError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.models import CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService, as_utc
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf
from .test_student_correction_reads import login


def returned(client, row, *, headers=None, **overrides):
    body = {"submission_version": row.submission_version, "reason": "Check the section shown on the submitted COR."}
    body.update(overrides)
    return client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/return", headers=csrf(client) if headers is None else headers, json=body)


def pending_unchanged(db, values):
    _, user, _, profile, row, _, path = values
    db.refresh(row)
    db.refresh(profile)
    assert row.status == "PENDING" and row.reviewed_at is row.reviewed_by_user_id is row.decision_reason is None
    assert profile.section == "A" and user.account_status == "ACTIVE"
    assert path.exists()
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "profile_change_returned", AuditEvent.target_id == row.change_request_id)) == 0


def test_return_is_trimmed_atomic_private_and_preserves_registered_context(db_session, db_client, evidence, caplog):
    _, user, screening, profile, row, file, path = evidence
    baseline, extraction = dict(row.registered_values_json), dict(row.extracted_values_json)
    deadline, validity = row.evidence_expires_at, screening.valid_until
    response = returned(db_client, row, reason=" \nPRIVATE-REASON: check the section.\t ")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["change_request"]["status"] == "RETURNED"
    assert body["change_request"]["decision_reason"] == "PRIVATE-REASON: check the section."
    assert body["change_request"]["reviewed_at"].endswith("Z")
    assert body["current_registered_values"]["section"] == profile.section == "A"
    assert body["registered_values_at_submission"] == baseline and body["extracted_values"] == extraction
    assert body["proposed_changes"] == {"section": "B"} and row.requested_section == "B"
    assert body["evidence"]["availability"] == "RESOLVED" and body["can_resubmit"] is False
    assert user.account_status == "ACTIVE" and screening.valid_until == validity
    assert as_utc(row.evidence_expires_at) == as_utc(deadline)
    assert not path.exists() and db_session.get(CorScreeningFile, file.cor_screening_file_id) is None
    audit = db_session.scalar(select(AuditEvent).where(AuditEvent.event_type == "profile_change_returned",
                                                      AuditEvent.target_id == row.change_request_id))
    assert audit.metadata_json == {"previous_status": "PENDING", "status": "RETURNED", "submission_version": 1}
    assert "PRIVATE-REASON" not in str(audit.metadata_json) + caplog.text
    for private in ("evidence_file_id", "evidence_sha256_hash", "storage_key", str(path)):
        assert private not in response.text
    login(db_client, user.email)
    own = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}")
    assert own.status_code == 200 and own.json()["change_request"]["decision_reason"] == "PRIVATE-REASON: check the section."
    assert "reviewed_by_user_id" not in own.text


@pytest.mark.parametrize("body", [{"reason": "Fix it"}, {"submission_version": 1},
    {"submission_version": True, "reason": "Fix it"}, {"submission_version": "1", "reason": "Fix it"},
    {"submission_version": 1.0, "reason": "Fix it"}, {"submission_version": 0, "reason": "Fix it"},
    {"submission_version": 1, "reason": None}, {"submission_version": 1, "reason": "x" * 501},
    {"submission_version": 1, "reason": "Fix it", "status": "PRIVATE-OVERRIDE"}])
def test_invalid_body_is_safe_and_has_no_side_effects(db_session, db_client, evidence, body, caplog):
    response = db_client.post(f"/api/v1/profile-change-requests/{evidence[4].change_request_id}/return",
                              headers=csrf(db_client), json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "PRIVATE-OVERRIDE" not in response.text + caplog.text
    pending_unchanged(db_session, evidence)


@pytest.mark.parametrize("reason", ["", " \t\n\u00a0 "])
def test_blank_reason_requires_actionable_text(db_session, db_client, evidence, reason):
    response = returned(db_client, evidence[4], reason=reason)
    assert response.status_code == 422 and response.json()["error"]["code"] == "CHANGE_REQUEST_REASON_REQUIRED"
    pending_unchanged(db_session, evidence)


def test_reason_length_is_applied_after_trimming(db_client, evidence):
    response = returned(db_client, evidence[4], reason="  " + "x" * 500 + "\n")
    assert response.status_code == 200
    assert response.json()["change_request"]["decision_reason"] == "x" * 500


@pytest.mark.parametrize("expected,provided", [(1, 2), (1, None), (None, 1)])
def test_wrong_version_cannot_return(db_session, db_client, evidence, expected, provided):
    row = evidence[4]
    row.submission_version = expected
    db_session.commit()
    response = returned(db_client, row, submission_version=provided)
    assert response.status_code == 409 and response.json()["error"]["code"] == "CHANGE_REQUEST_VERSION_CONFLICT"
    pending_unchanged(db_session, evidence)


def test_legacy_return_requires_explicit_null_and_preserves_unknown_context(db_session, db_client, evidence):
    row = evidence[4]
    row.submission_version = None
    row.extracted_values_json = row.registered_values_json = None
    db_session.commit()
    response = returned(db_client, row, submission_version=None)
    assert response.status_code == 200
    body = response.json()
    assert body["change_request"]["status"] == "RETURNED" and body["change_request"]["submission_version"] is None
    assert body["extracted_values"] is body["registered_values_at_submission"] is body["changed_fields"] is None
    assert row.submission_version is None and not evidence[-1].exists()


@pytest.mark.parametrize("unavailable", ["missing_bytes", "missing_metadata", "expired", "failed_cleanup", "stale_profile"])
def test_unusable_evidence_or_stale_profile_does_not_prevent_reasoned_return(db_session, db_client, evidence, unavailable):
    _, _, _, profile, row, file, path = evidence
    if unavailable == "missing_bytes":
        path.unlink()
    elif unavailable == "missing_metadata":
        db_session.delete(file)
    elif unavailable == "expired":
        row.evidence_uploaded_at = datetime.now(timezone.utc) - timedelta(days=8)
        row.evidence_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif unavailable == "failed_cleanup":
        file.cleanup_state = "FAILED"
    else:
        profile.section = "NEWER-REGISTERED"
    db_session.commit()
    response = returned(db_client, row)
    assert response.status_code == 200 and row.status == "RETURNED"
    assert profile.section == ("NEWER-REGISTERED" if unavailable == "stale_profile" else "A")
    # Deliberately lost metadata provides no authorized storage location;
    # cleanup must not guess paths or sweep unrelated private files.
    assert path.exists() == (unavailable == "missing_metadata")


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED", "RETURNED"])
def test_historical_terminal_decision_cannot_be_rewritten(db_session, db_client, evidence, status):
    row = evidence[4]
    row.status, row.decision_reason = status, "Original historical reason"
    db_session.commit()
    response = returned(db_client, row)
    assert response.status_code == 409 and response.json()["error"]["code"] == "CHANGE_REQUEST_NOT_PENDING"
    db_session.refresh(row)
    assert row.status == status and row.decision_reason == "Original historical reason"


def test_obsolete_version_cannot_be_returned(db_session, db_client, evidence):
    row = evidence[4]
    child = ProfileChangeRequest(student_user_id=row.student_user_id, cor_screening_id=row.cor_screening_id,
        root_change_request_id=row.change_request_id, previous_change_request_id=row.change_request_id,
        submission_version=2, status="RETURNED", requested_first_name="Juan", requested_middle_name="Dela",
        requested_last_name="Cruz", requested_year_level=1, requested_section="B")
    db_session.add(child)
    db_session.commit()
    response = returned(db_client, row)
    assert response.status_code == 409 and response.json()["error"]["code"] == "CHANGE_REQUEST_VERSION_CONFLICT"
    pending_unchanged(db_session, evidence)


@pytest.mark.parametrize("role", ["STUDENT", "COUNSELOR", "GUIDANCE_STAFF"])
def test_other_roles_cannot_return(db_session, db_client, evidence, role):
    if role == "STUDENT":
        actor = evidence[1]
    else:
        actor = User(email="return-staff@example.edu", password_hash=hash_password("password1"), role_code=role,
                     account_status="ACTIVE", first_name="Staff", last_name="Reader")
        db_session.add(actor)
        db_session.commit()
    login(db_client, actor.email)
    response = returned(db_client, evidence[4])
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN_ROLE"
    pending_unchanged(db_session, evidence)


def test_deactivated_reviewer_cannot_return(db_session, db_client, evidence):
    headers = csrf(db_client)
    actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
    actor.is_deactivated = True
    db_session.commit()
    response = returned(db_client, evidence[4], headers=headers)
    assert response.status_code == 403 and response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"
    pending_unchanged(db_session, evidence)


def test_session_csrf_and_authentication_remain_required(db_session, db_client, evidence):
    row = evidence[4]
    response = db_client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/return",
                             json={"submission_version": 1, "reason": "Fix it"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
    db_client.cookies.clear()
    for headers in ({}, {"X-COR-Token": "not-a-session"}):
        response = db_client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/return", headers=headers,
                                 json={"submission_version": 1, "reason": "Fix it"})
        assert response.status_code == 401
    pending_unchanged(db_session, evidence)


@pytest.mark.parametrize("failure", ["audit", "database"])
def test_failed_return_rolls_back_without_releasing_cor(db_session, db_client, evidence, monkeypatch, failure, caplog):
    row = evidence[4]
    original = AuditService.record

    def fail(self, actor_id, event_type, target_type, target_id, **kwargs):
        original(self, actor_id, event_type, target_type, target_id, **kwargs)
        if event_type == "profile_change_returned":
            self.repository.session.flush()
            if failure == "database":
                raise OperationalError("PRIVATE-SQL", {"reason": "PRIVATE-REASON"}, MysqlOperationalError(1213, "PRIVATE-DRIVER"))
            raise RuntimeError("Injected return audit failure")

    monkeypatch.setattr(AuditService, "record", fail)
    if failure == "database":
        response = returned(db_client, row, reason="PRIVATE-REASON")
        assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert not any(private in response.text + caplog.text for private in ("PRIVATE-SQL", "PRIVATE-REASON", "PRIVATE-DRIVER"))
    else:
        actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
        with pytest.raises(RuntimeError, match="Injected return audit failure"):
            ProfileChangeService(db_session).return_request(actor, row.change_request_id, "Fix it", submission_version=1)
    pending_unchanged(db_session, evidence)


def test_repeated_return_is_a_conflict_and_deletion_failure_stays_retryable(db_session, db_client, evidence, monkeypatch):
    _, _, _, _, row, file, path = evidence
    monkeypatch.setattr(CorScreeningService, "_delete_cor_bytes", lambda *_: False)
    response = returned(db_client, row)
    assert response.status_code == 200 and response.json()["evidence"]["availability"] == "RESOLVED"
    db_session.refresh(file)
    assert file.cleanup_state == "FAILED" and path.exists()
    second = returned(db_client, row, reason="Another reason")
    assert second.status_code == 409 and second.json()["error"]["code"] == "CHANGE_REQUEST_NOT_PENDING"
    assert row.decision_reason == "Check the section shown on the submitted COR."


@pytest.mark.parametrize("failure", ["flush", "commit"])
def test_failed_return_write_or_commit_explicitly_rolls_back(db_session, evidence, monkeypatch, failure):
    row = evidence[4]
    actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
    if failure == "flush":
        original = db_session.flush
        injected = []

        def fail(*args, **kwargs):
            result = original(*args, **kwargs)
            if not injected and row.status == "RETURNED":
                injected.append(True)
                raise RuntimeError("Injected return flush failure")
            return result

        monkeypatch.setattr(db_session, "flush", fail)
    else:
        def fail():
            raise RuntimeError("Injected return commit failure")

        monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(RuntimeError, match="Injected return"):
        ProfileChangeService(db_session).return_request(actor, row.change_request_id, "Fix it", submission_version=1)
    pending_unchanged(db_session, evidence)
