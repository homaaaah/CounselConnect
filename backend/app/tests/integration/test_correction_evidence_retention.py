"""Bounded pending-review retention through the existing COR cleanup flow."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.models import CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.service import ProfileChangeService
from .test_profile_change import _payload, _register, _superadmin, good_result, stub_screening


def pending(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)
    evidence = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(evidence.storage_key))
    _scr, _user, profile, request = service.request_edit(user, _payload(campus_id, program_id, section="B"))
    assert path.exists()
    return service, user, screening, profile, request, evidence, path


def advance(monkeypatch, days):
    moment = datetime.now(timezone.utc) + timedelta(days=days)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz is not None else moment.replace(tzinfo=None)

    monkeypatch.setattr("app.modules.cor_screening.service.datetime", Clock)
    monkeypatch.setattr("app.modules.profile_change.service.datetime", Clock)


def test_pending_survives_cleanup_without_extending_original_deadline(db_session, academic_references, monkeypatch):
    service, user, screening, profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    original = evidence.expires_at
    for _ in range(2):
        service.cleanup_due_files()
        db_session.refresh(request)
        db_session.refresh(evidence)
        assert request.status == "PENDING"
        assert evidence.expires_at == original
        assert request.evidence_expires_at == original
        assert path.exists()
    assert user.account_status == "ACTIVE"
    assert screening.status == "PASSED"
    assert profile.section == "A"


def test_expiry_returns_request_deletes_evidence_and_preserves_enrollment(db_session, academic_references, monkeypatch):
    service, user, screening, profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    validity = screening.valid_until
    original_deadline = request.evidence_expires_at
    advance(monkeypatch, 8)
    service.cleanup_due_files()
    db_session.refresh(request)
    assert request.status == "RETURNED"
    assert request.decision_reason == "COR_EVIDENCE_EXPIRED"
    assert request.reviewed_by_user_id is None
    assert request.reviewed_at is not None
    assert request.evidence_expires_at == original_deadline
    assert not path.exists()
    assert db_session.get(CorScreeningFile, evidence.cor_screening_file_id) is None
    assert user.account_status == "ACTIVE"
    assert screening.status == "PASSED"
    assert screening.valid_until == validity
    assert profile.section == "A"
    assert request.requested_section == "B"
    service.cleanup_due_files()
    events = list(db_session.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_returned")))
    assert len(events) == 1
    assert events[0].actor_user_id is None
    assert events[0].metadata_json == {"status": "RETURNED", "submission_version": 1, "reason_code": "COR_EVIDENCE_EXPIRED"}
    actor = _superadmin(db_session)
    assert ProfileChangeService(db_session).list_requests(actor, status="RETURNED").items[0].change_request.status == "RETURNED"


def test_original_request_deadline_wins_over_extended_file_metadata(db_session, academic_references, monkeypatch):
    service, _user, _scr, _profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    evidence.expires_at += timedelta(days=30)
    db_session.commit()
    advance(monkeypatch, 8)
    service.cleanup_due_files()
    db_session.refresh(request)
    assert request.status == "RETURNED"
    assert request.decision_reason == "COR_EVIDENCE_EXPIRED"
    assert not path.exists()


def test_missing_file_metadata_still_expires_request(db_session, academic_references, monkeypatch):
    service, _user, screening, _profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    path.unlink()
    db_session.delete(evidence)
    db_session.commit()
    advance(monkeypatch, 8)
    service.cleanup_due_files()
    db_session.refresh(request)
    assert request.status == "RETURNED"
    assert request.decision_reason == "COR_EVIDENCE_EXPIRED"
    assert screening.status == "PASSED"


def test_metadata_digest_mismatch_is_not_a_retention_hold(db_session, academic_references, monkeypatch):
    service, user, _scr, _profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    original = request.evidence_sha256_hash
    evidence.sha256_hash = b"z" * 32
    db_session.commit()
    service.cleanup_due_files()
    db_session.refresh(request)
    assert request.status == "RETURNED"
    assert request.decision_reason == "COR_EVIDENCE_UNAVAILABLE"
    assert request.evidence_sha256_hash == original
    assert user.account_status == "ACTIVE"
    assert not path.exists()


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_committed_decision_releases_cor_immediately(db_session, academic_references, monkeypatch, decision):
    _service, _user, _scr, profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    actor = _superadmin(db_session)
    reviews = ProfileChangeService(db_session)
    if decision == "approve":
        reviews.approve(actor, request.change_request_id, submission_version=1)
        assert request.status == "APPROVED"
        assert profile.section == "B"
    else:
        reviews.reject(actor, request.change_request_id, "Review the section on the submitted COR.", submission_version=1)
        assert request.status == "RETURNED"  # Reject is now the version-bound return alias.
        assert profile.section == "A"
    assert not path.exists()
    assert db_session.get(CorScreeningFile, evidence.cor_screening_file_id) is None


def test_expired_approval_denied_before_cleanup_runs(db_session, academic_references, monkeypatch):
    _service, user, _scr, profile, request, _evidence, path = pending(db_session, academic_references, monkeypatch)
    actor = _superadmin(db_session)
    advance(monkeypatch, 8)
    with pytest.raises(AppError) as error:
        ProfileChangeService(db_session).approve(actor, request.change_request_id, submission_version=1)
    assert error.value.code == "COR_EVIDENCE_UNAVAILABLE"
    assert request.status == "PENDING"
    assert profile.section == "A"
    assert user.account_status == "ACTIVE"
    assert path.exists()  # Cleanup has not run; denial does not apply changes.


def test_cleanup_failure_is_retried_after_a_decision(db_session, academic_references, monkeypatch, caplog):
    service, _user, _scr, _profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    actor = _superadmin(db_session)
    key = evidence.storage_key
    with monkeypatch.context() as patch:
        patch.setattr(CorScreeningService, "_delete_cor_bytes", lambda self, key: False)
        ProfileChangeService(db_session).approve(actor, request.change_request_id, submission_version=1)
    db_session.refresh(evidence)
    assert evidence.cleanup_state == "FAILED"
    assert request.status == "APPROVED"
    assert path.exists()
    assert key not in caplog.text
    service.cleanup_due_files()
    assert not path.exists()
    assert db_session.get(CorScreeningFile, evidence.cor_screening_file_id) is None


def test_return_audit_failure_keeps_bytes_and_retries(db_session, academic_references, monkeypatch):
    service, user, _scr, _profile, request, _evidence, path = pending(db_session, academic_references, monkeypatch)
    advance(monkeypatch, 8)
    record = AuditService.record

    def fail_return(self, actor, event_type, target_type, target_id, **kwargs):
        if event_type == "profile_change_returned":
            raise RuntimeError("Injected return audit failure")
        return record(self, actor, event_type, target_type, target_id, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(AuditService, "record", fail_return)
        service.cleanup_due_files()
    db_session.refresh(request)
    assert request.status == "PENDING"
    assert path.exists()
    assert user.account_status == "ACTIVE"
    service.cleanup_due_files()
    db_session.refresh(request)
    assert request.status == "RETURNED"
    assert not path.exists()
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "profile_change_returned")) == 1


def test_new_enrollment_upload_releases_old_pending_evidence(db_session, academic_references, monkeypatch):
    service, user, screening, _profile, request, _evidence, old_path = pending(db_session, academic_references, monkeypatch)
    screening.valid_until = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    user.account_status = "VERIFICATION_EXPIRED"
    db_session.commit()
    replacement, _token = service.resubmit(user, b"%PDF-1.4 replacement", "cor.pdf")
    db_session.refresh(request)
    assert request.status == "RETURNED"
    assert request.decision_reason == "SUPERSEDED_BY_NEW_COR"
    assert not old_path.exists()
    new_file = service.repository.find_active_file(replacement.cor_screening_id)
    assert new_file is not None
    assert Path(service._storage_path(new_file.storage_key)).exists()
    assert replacement.status == "AWAITING_CONFIRMATION"
    assert user.account_status == "VERIFICATION_EXPIRED"


def test_no_change_confirmation_still_deletes_cor_immediately(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)
    evidence = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(evidence.storage_key))
    _scr, _user, _profile, request = service.request_edit(user, _payload(campus_id, program_id))
    assert request is None
    assert user.account_status == "ACTIVE"
    assert not path.exists()


def test_superseding_unknown_legacy_context_preserves_old_rejection_semantics(
    db_session, academic_references, monkeypatch
):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)
    reviews = ProfileChangeService(db_session)
    legacy = reviews.create_pending(user, screening.cor_screening_id, first_name="Juan", middle_name="Dela",
                                    last_name="Cruz", year_level=1, section="B")
    reviews.supersede_pending(user.user_id)
    assert legacy.submission_version is None
    assert legacy.status == "REJECTED"
    assert legacy.decision_reason == "SUPERSEDED_BY_NEW_COR"
    assert legacy.extracted_values_json is None


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_failed_decision_audit_cannot_release_evidence(db_session, academic_references, monkeypatch, decision):
    _service, _user, _scr, profile, request, _evidence, path = pending(db_session, academic_references, monkeypatch)
    actor = _superadmin(db_session)
    record = AuditService.record

    def fail_decision(self, actor_id, event_type, target_type, target_id, **kwargs):
        if event_type in {"profile_change_approved", "profile_change_returned"}:
            raise RuntimeError("Injected decision audit failure")
        return record(self, actor_id, event_type, target_type, target_id, **kwargs)

    monkeypatch.setattr(AuditService, "record", fail_decision)
    reviews = ProfileChangeService(db_session)
    with pytest.raises(RuntimeError, match="Injected decision audit failure"):
        if decision == "approve":
            reviews.approve(actor, request.change_request_id, submission_version=1)
        else:
            reviews.reject(actor, request.change_request_id, "Check the section.", submission_version=1)
    db_session.rollback()
    db_session.refresh(request)
    db_session.refresh(profile)
    assert request.status == "PENDING"
    assert profile.section == "A"
    assert path.exists()
