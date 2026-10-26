"""Approval returns the same safe post-decision detail as the review GET."""

from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf
from .test_student_correction_reads import login


def approve(client, request):
    return client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve",
                       headers=csrf(client), json={"submission_version": 1})


def test_success_returns_post_commit_current_values_and_immutable_review_context(db_session, db_client, evidence):
    _, user, screening, profile, row, file, path = evidence
    extracted = dict(row.extracted_values_json)
    baseline = dict(row.registered_values_json)
    response = approve(db_client, row)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"change_request", "student", "extracted_values", "registered_values_at_submission",
        "current_registered_values", "proposed_changes", "changed_fields", "evidence", "history", "can_resubmit"}
    assert body["change_request"]["status"] == "APPROVED"
    assert body["change_request"]["change_request_id"] == row.change_request_id
    assert body["change_request"]["submission_version"] == 1
    assert body["student"]["user_id"] == user.user_id
    assert body["current_registered_values"]["section"] == profile.section == "B"
    assert body["registered_values_at_submission"] == baseline
    assert body["extracted_values"] == extracted
    assert body["proposed_changes"] == {"section": "B"} and body["changed_fields"] == ["section"]
    assert body["evidence"]["availability"] == "RESOLVED" and body["evidence"]["expires_at"].endswith("Z")
    assert body["can_resubmit"] is False
    assert len(body["history"]) == 1 and body["history"][0]["status"] == "APPROVED"
    assert body["change_request"]["reviewed_at"].endswith("Z")
    assert body["history"][0]["reviewed_by_user_id"] == body["change_request"]["reviewed_by_user_id"]
    assert not path.exists() and db_session.get(CorScreeningFile, file.cor_screening_file_id) is None
    audits = list(db_session.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_approved",
        AuditEvent.target_id == row.change_request_id)))
    assert len(audits) == 1
    detail = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}")
    assert detail.status_code == 200 and detail.json() == body
    assert screening.status == "PASSED" and user.account_status == "ACTIVE"


def test_success_filters_private_extra_snapshot_keys(db_session, db_client, evidence, caplog):
    _, _, _, _, row, _, path = evidence
    extra = {"storage_key": "PRIVATE-PATH", "token": "PRIVATE-TOKEN", "clinical_note": "PRIVATE-CLINICAL"}
    row.registered_values_json = {**row.registered_values_json, **extra}
    row.extracted_values_json = {**row.extracted_values_json, **extra}
    db_session.commit()
    response = approve(db_client, row)
    assert response.status_code == 200
    for private in (*extra.keys(), *extra.values(), str(path), "evidence_file_id", "evidence_sha256_hash", "validation_results_json"):
        assert private not in response.text + caplog.text


def test_failed_cleanup_cannot_make_resolved_evidence_available_in_success_detail(db_session, db_client, evidence, monkeypatch):
    _, _, _, _, row, file, path = evidence
    monkeypatch.setattr(CorScreeningService, "_delete_cor_bytes", lambda *_: False)
    response = approve(db_client, row)
    assert response.status_code == 200
    assert response.json()["change_request"]["status"] == "APPROVED"
    assert response.json()["evidence"]["availability"] == "RESOLVED"
    db_session.refresh(file)
    assert file.cleanup_state == "FAILED" and path.exists()
    preview = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}/cor")
    assert preview.status_code == 409
    assert preview.json()["error"]["details"]["availability"] == "RESOLVED"


def test_student_reads_remain_narrow_after_approval(db_client, evidence):
    _, user, _, _, row, _, _ = evidence
    assert approve(db_client, row).status_code == 200
    login(db_client, user.email)
    response = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}")
    assert response.status_code == 200
    assert response.json()["change_request"]["status"] == "APPROVED"
    assert response.json()["current_section"] == "B"
    assert response.json()["registered_values_at_submission"]["section"] == "A"
    for private in ("student", "extracted_values", "history", "evidence", "reviewed_by_user_id"):
        assert private not in response.json() and private not in response.json()["change_request"]
