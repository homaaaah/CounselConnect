"""Exact correction cleanup never changes the separate enrolled baseline."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_evidence_retention import pending
from .test_profile_change import _superadmin


def separate_proof(db, academic_references, monkeypatch):
    service, user, enrolled, profile, request, file, path = pending(db, academic_references, monkeypatch)
    # Test-only future proof layout: no application endpoint creates these yet.
    proof = CorScreening(
        student_user_id=user.user_id, purpose="CORRECTION", status="PASSED",
        format_template_version="test", submitted_at=enrolled.submitted_at,
    )
    db.add(proof)
    db.flush()
    request.cor_screening_id = proof.cor_screening_id
    file.cor_screening_id = proof.cor_screening_id
    db.commit()
    return service, user, enrolled, profile, request, file, path, proof


def freeze(monkeypatch, moment):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)
    monkeypatch.setattr("app.modules.cor_screening.service.datetime", Clock)
    monkeypatch.setattr("app.modules.profile_change.service.datetime", Clock)


@pytest.mark.parametrize("failure", [False, True])
def test_correction_expiry_returns_only_exact_request_and_retries_bytes(
    db_session, academic_references, monkeypatch, failure,
):
    service, user, enrolled, profile, request, file, path, proof = separate_proof(db_session, academic_references, monkeypatch)
    validity = enrolled.valid_until
    original_deadline = request.evidence_expires_at
    service.cleanup_due_files()
    assert path.exists()
    assert request.status == "PENDING"
    freeze(monkeypatch, datetime.now(timezone.utc) + timedelta(days=8))
    with monkeypatch.context() as patch:
        if failure:
            patch.setattr(service, "_delete_cor_bytes", lambda key: False)
        service.cleanup_due_files()
    assert request.status == "RETURNED"
    assert request.decision_reason == "COR_EVIDENCE_EXPIRED"
    assert request.evidence_expires_at == original_deadline
    if failure:
        assert path.exists()
        assert file.cleanup_state == "FAILED"
    service.cleanup_due_files()
    assert not path.exists()
    assert db_session.get(CorScreeningFile, file.cor_screening_file_id) is None
    assert user.account_status == "ACTIVE"
    assert enrolled.status == "PASSED"
    assert enrolled.valid_until == validity
    assert enrolled.confirmed_at is not None
    assert proof.confirmed_at is None
    assert profile.section == "A"
    assert request.registered_cor_screening_id == enrolled.cor_screening_id
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "profile_change_returned")) == 1


def test_manual_return_of_correction_releases_only_its_evidence(db_session, academic_references, monkeypatch):
    service, user, enrolled, profile, request, file, path, proof = separate_proof(db_session, academic_references, monkeypatch)
    validity = enrolled.valid_until
    ProfileChangeService(db_session).return_request(
        _superadmin(db_session), request.change_request_id, "Recheck the section.", submission_version=1,
    )
    assert request.status == "RETURNED"
    assert not path.exists()
    assert db_session.get(CorScreeningFile, file.cor_screening_file_id) is None
    assert enrolled.status == "PASSED"
    assert enrolled.valid_until == validity
    assert user.account_status == "ACTIVE"
    assert profile.section == "A"
    assert proof.confirmed_at is None


def test_pending_hold_cannot_outlast_original_file_upload(db_session, academic_references, monkeypatch):
    service, user, enrolled, profile, request, file, path, proof = separate_proof(db_session, academic_references, monkeypatch)
    uploaded = file.uploaded_at.replace(tzinfo=timezone.utc)
    file.expires_at += timedelta(days=30)
    request.evidence_uploaded_at += timedelta(days=1)
    request.evidence_expires_at += timedelta(days=30)
    db_session.commit()
    freeze(monkeypatch, uploaded + timedelta(days=7))
    service.cleanup_due_files()
    assert request.status == "RETURNED"
    assert request.decision_reason == "COR_EVIDENCE_EXPIRED"
    assert not path.exists()
    assert user.account_status == "ACTIVE"
    assert enrolled.status == "PASSED"
    assert profile.section == "A"


@pytest.mark.parametrize("purpose", ["REGISTRATION", "CORRECTION"])
def test_open_file_original_upload_limit_wins_over_extended_metadata(
    db_session, academic_references, monkeypatch, purpose,
):
    service, user, enrolled, profile, request, file, path, proof = separate_proof(db_session, academic_references, monkeypatch)
    proof.purpose = purpose
    proof.status = "AWAITING_CONFIRMATION"
    request.status = "RETURNED"  # No pending retention hold; exercise open-file path.
    file.expires_at += timedelta(days=30)
    db_session.commit()
    uploaded = file.uploaded_at.replace(tzinfo=timezone.utc)
    # Keep submitted_at younger than the file so the file predicate must select it.
    proof.submitted_at = uploaded + timedelta(days=1)
    db_session.commit()
    freeze(monkeypatch, uploaded + timedelta(days=7) - timedelta(microseconds=1))
    service.cleanup_screening_files(proof.cor_screening_id)
    assert path.exists()
    freeze(monkeypatch, uploaded + timedelta(days=7))
    assert proof.cor_screening_id in service.repository.list_cleanup_candidates(uploaded + timedelta(days=7))
    service.cleanup_due_files()
    assert not path.exists()
    assert db_session.get(CorScreeningFile, file.cor_screening_file_id) is None
    assert proof.status == "AWAITING_CONFIRMATION"
    assert enrolled.status == "PASSED"
    assert user.account_status == "ACTIVE"
    assert profile.section == "A"
