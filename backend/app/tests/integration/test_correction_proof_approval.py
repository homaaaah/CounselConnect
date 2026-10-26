"""Separate proof approval changes supported profile fields, never enrollment."""

from copy import deepcopy
from datetime import timedelta

import pytest

from app.core.exceptions import AppError
from app.modules.audit.service import AuditService
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_proof_reads import proof_context  # noqa: F401
from .test_correction_approval_transaction import decisions
from .test_correction_approval_version import csrf
from .test_profile_change import _superadmin
from .test_student_correction_reads import login


@pytest.mark.parametrize("unmapped", [False, True])
def test_separate_proof_approval_preserves_enrollment_and_snapshots(db_session, db_client, proof_context, unmapped):
    service, user, enrolled, profile, request, file, path, proof = proof_context
    if unmapped:
        proof.extracted_campus_id = proof.extracted_program_id = None
        proof.extracted_academic_period = None
        db_session.commit()
    original = (enrolled.status, enrolled.valid_until, enrolled.confirmed_at, user.account_status,
                profile.student_number, profile.campus_id, profile.program_id)
    snapshots = deepcopy((request.registered_values_json, request.extracted_values_json))
    actor = _superadmin(db_session)
    login(db_client, actor.email, "super-pass-1")
    result = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve",
        headers=csrf(db_client), json={"submission_version": 1})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["change_request"]["status"] == "APPROVED"
    assert result.json()["evidence"]["availability"] == "RESOLVED"
    assert profile.section == "B"
    assert original == (enrolled.status, enrolled.valid_until, enrolled.confirmed_at, user.account_status,
                        profile.student_number, profile.campus_id, profile.program_id)
    assert snapshots == (request.registered_values_json, request.extracted_values_json)
    assert proof.confirmed_at is None and proof.valid_until is None
    assert not path.exists()
    assert len(decisions(db_session, request)) == 1


@pytest.mark.parametrize("field", ["first_name", "section", "year_level", "academic_period", "valid_until"])
def test_separate_proof_approval_rejects_changed_registered_baseline(db_session, proof_context, field):
    service, user, enrolled, profile, request, file, path, proof = proof_context
    if field == "first_name":
        user.first_name = "New name"
    elif field == "section":
        profile.section = "NEW"
    elif field == "year_level":
        profile.year_level = 2
    elif field == "academic_period":
        enrolled.extracted_academic_period = "2099-2100"
        proof.extracted_academic_period = "2099-2100"  # Still matches live proof; immutable baseline must win.
    else:
        enrolled.valid_until += timedelta(days=1)
    db_session.commit()
    actor = _superadmin(db_session)
    with pytest.raises(AppError) as caught:
        ProfileChangeService(db_session).approve(actor, request.change_request_id, submission_version=1)
    assert caught.value.code == "CHANGE_REQUEST_STALE"
    assert request.status == "PENDING"
    assert path.exists() and decisions(db_session, request) == []


def test_separate_proof_approval_audit_failure_rolls_back_before_cleanup(db_session, proof_context, monkeypatch):
    service, user, enrolled, profile, request, file, path, proof = proof_context
    actor = _superadmin(db_session)
    record = AuditService.record
    def fail(self, actor_id, event_type, *args, **kwargs):
        if event_type == "profile_change_approved":
            raise RuntimeError("Injected audit failure")
        return record(self, actor_id, event_type, *args, **kwargs)
    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        ProfileChangeService(db_session).approve(actor, request.change_request_id, submission_version=1)
    db_session.refresh(profile)
    db_session.refresh(request)
    assert profile.section == "A" and request.status == "PENDING"
    assert enrolled.status == "PASSED" and user.account_status == "ACTIVE"
    assert proof.confirmed_at is None and proof.valid_until is None
    assert path.exists() and decisions(db_session, request) == []
