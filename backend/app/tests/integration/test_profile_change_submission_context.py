"""Initial submission snapshots, evidence binding, and transaction boundaries."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.service import CorScreeningService, as_utc
from app.modules.profile_change.models import ProfileChangeRequest
from .test_profile_change import _payload, _register, good_result, stub_screening


def test_submission_preserves_original_extraction_baseline_and_exact_evidence(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    result = good_result(campus="Unmapped Campus", course="Unmapped Program")
    result.fields.name = "Juan Cruz"
    result.fields.section = " A\t 1 "
    result.fields.valid_until = (datetime.now(timezone.utc) + timedelta(days=90)).date().isoformat()
    stub_screening(monkeypatch, result)
    service = CorScreeningService(db_session)
    # Production sessions disable autoflush. Match that setting while the
    # screening mapper performs reference lookups during finalization.
    with db_session.no_autoflush:
        user, screening = _register(service)
    evidence = service.repository.find_active_file(screening.cor_screening_id)
    evidence_id, digest = evidence.cor_screening_file_id, evidence.sha256_hash
    uploaded, expires = evidence.uploaded_at, evidence.expires_at
    path = Path(service._storage_path(evidence.storage_key))
    _scr, activated, profile, request = service.request_edit(
        user, _payload(campus_id, program_id, middle_name="Maria", section="A 1")
    )
    db_session.refresh(request)
    extraction = {
        "student_number": "20231234-A", "first_name": "Juan", "middle_name": None,
        "last_name": "Cruz", "campus_id": None, "program_id": None, "year_level": 1,
        "section": " A\t 1 ", "academic_period": "2026-2027", "valid_until": result.fields.valid_until,
    }
    baseline = {**extraction, "campus_id": campus_id, "program_id": program_id, "section": "A 1"}
    assert request.extracted_values_json == extraction
    assert request.registered_values_json == baseline
    assert request.submission_version == 1
    assert request.previous_change_request_id is None
    assert request.root_change_request_id is None
    assert request.student_user_id == activated.user_id
    assert request.cor_screening_id == screening.cor_screening_id
    assert request.registered_cor_screening_id == screening.cor_screening_id
    assert request.evidence_file_id == evidence_id
    assert request.evidence_sha256_hash == digest
    assert request.evidence_uploaded_at == uploaded
    assert request.evidence_expires_at == expires
    assert as_utc(expires) - as_utc(uploaded) <= timedelta(days=7)
    assert activated.middle_name is None
    assert request.requested_middle_name == "Maria"
    # Task 4.3 retains only this exact file until decision or original expiry.
    assert path.exists()
    assert service.repository.find_active_file(screening.cor_screening_id).cor_screening_file_id == evidence_id
    assert screening.extracted_campus_id == campus_id  # _activate mutates the source.
    screening.extracted_section = "Later extraction"
    activated.first_name = "Later name"
    profile.section = "Later profile"
    db_session.commit()
    db_session.refresh(request)
    assert request.extracted_values_json == extraction
    assert request.registered_values_json == baseline
    assert request.requested_middle_name == "Maria"
    assert request.evidence_file_id == evidence_id


def test_renewal_snapshot_is_new_confirmation_baseline_not_fabricated_history(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, old = _register(service)
    service.confirm(user, _payload(campus_id, program_id))
    old.valid_until = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    user.account_status = "VERIFICATION_EXPIRED"
    profile = service.accounts.find_student_profile(user.user_id)
    profile.section = "Previously registered section"
    db_session.commit()
    renewal, _token = service.resubmit(user, b"%PDF-1.4 renewed", "renewal.pdf")
    _scr, activated, profile, request = service.request_edit(user, _payload(campus_id, program_id, section="B"))
    assert request.registered_cor_screening_id == renewal.cor_screening_id
    assert request.registered_cor_screening_id != old.cor_screening_id
    assert request.registered_values_json["section"] == "A"
    assert request.extracted_values_json["section"] == "A"
    assert profile.section == "A"
    assert request.requested_section == "B"
    assert activated.account_status == "ACTIVE"


@pytest.mark.parametrize("unavailable", ["missing", "expired", "cleanup_failed"])
def test_no_context_is_submitted_without_eligible_file_metadata(
    db_session, academic_references, monkeypatch, unavailable
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)
    evidence = service.repository.find_active_file(screening.cor_screening_id)
    if unavailable == "missing":
        db_session.delete(evidence)
    elif unavailable == "expired":
        evidence.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    else:
        evidence.cleanup_state = "FAILED"
    db_session.commit()
    with pytest.raises(AppError) as error:
        service.request_edit(user, _payload(campus_id, program_id, section="B"))
    assert error.value.code == "COR_EVIDENCE_UNAVAILABLE"
    assert user.account_status == "PENDING_VERIFICATION"
    assert screening.status == "AWAITING_CONFIRMATION"
    assert db_session.scalar(select(func.count()).select_from(ProfileChangeRequest)) == 0


def test_resolved_submission_cannot_bind_another_students_screening(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    owner, screening = _register(service)
    other = User(email="other@example.test", password_hash="unused", first_name="Other", last_name="Student",
                 role_code="STUDENT", account_status="PENDING_VERIFICATION")
    db_session.add(other)
    db_session.flush()
    with pytest.raises(AppError) as error:
        service.request_edit_resolved(other, screening, _payload(campus_id, program_id, section="B"))
    assert error.value.code == "SCREENING_NOT_FOUND"
    assert owner.account_status == other.account_status == "PENDING_VERIFICATION"
    assert db_session.scalar(select(func.count()).select_from(ProfileChangeRequest)) == 0


def test_review_only_screening_cannot_establish_registration_snapshot(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)
    screening.purpose = "CORRECTION"
    db_session.commit()
    with pytest.raises(AppError) as error:
        service.request_edit(user, _payload(campus_id, program_id, section="B"))
    assert error.value.code == "SCREENING_NOT_FOUND"
    assert user.account_status == "PENDING_VERIFICATION"


def test_duplicate_submission_does_not_replace_snapshot_or_add_a_version(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service)
    _scr, _user, _profile, request = service.request_edit(user, _payload(campus_id, program_id, section="B"))
    baseline, extraction = request.registered_values_json, request.extracted_values_json
    with pytest.raises(AppError) as error:
        service.request_edit(user, _payload(campus_id, program_id, section="C"))
    assert error.value.code == "SCREENING_NOT_CONFIRMABLE"
    db_session.refresh(request)
    assert db_session.scalar(select(func.count()).select_from(ProfileChangeRequest)) == 1
    assert request.registered_values_json == baseline
    assert request.extracted_values_json == extraction
    assert request.requested_section == "B"
    assert request.submission_version == 1


def test_audit_failure_rolls_back_activation_submission_and_preserves_evidence(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)
    evidence = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(evidence.storage_key))
    record = AuditService.record

    def fail_submission_audit(self, actor, event_type, target_type, target_id, **kwargs):
        if event_type == "profile_change_requested":
            raise RuntimeError("Injected audit failure")
        return record(self, actor, event_type, target_type, target_id, **kwargs)

    monkeypatch.setattr(AuditService, "record", fail_submission_audit)
    with pytest.raises(RuntimeError, match="Injected audit failure"):
        service.request_edit(user, _payload(campus_id, program_id, section="B"))
    db_session.rollback()
    db_session.refresh(user)
    db_session.refresh(screening)
    assert user.account_status == "PENDING_VERIFICATION"
    assert screening.status == "AWAITING_CONFIRMATION"
    assert screening.verification_token_hash is not None
    assert path.exists()
    assert db_session.scalar(select(func.count()).select_from(ProfileChangeRequest)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type.in_(["account_activated", "profile_change_requested"]))) == 0


def test_snapshot_context_stays_private_and_submission_audit_is_committed(
    db_session, db_client, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, token = service.register_with_cor(
        "context@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    response = db_client.post("/api/v1/cor-screenings/request-edit", headers={"X-COR-Token": token},
                              json=_payload(campus_id, program_id, section="B").model_dump())
    assert response.status_code == 200
    request = db_session.scalar(select(ProfileChangeRequest))
    assert request.submission_version == 1
    assert not {"extracted_values_json", "registered_values_json", "evidence_file_id",
                "evidence_sha256_hash", "evidence_uploaded_at", "evidence_expires_at"} & response.json()["change_request"].keys()
    events = list(db_session.scalars(select(AuditEvent).where(AuditEvent.event_type.in_(
        ["account_activated", "profile_change_requested"]))))
    assert {event.event_type for event in events} == {"account_activated", "profile_change_requested"}
    for event in events:
        assert event.actor_user_id == user.user_id
        assert event.outcome == "SUCCESS"
        assert event.occurred_at is not None
        expected = ({"status": "ACTIVE"} if event.event_type == "account_activated" else
                    {"status": "PENDING", "submission_version": 1})
        assert event.metadata_json == expected
    assert next(event for event in events if event.event_type == "profile_change_requested").target_id == request.change_request_id
