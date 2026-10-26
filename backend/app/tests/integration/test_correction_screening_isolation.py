"""Correction evidence cannot serve as registration state or credentials."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AppError
from app.core.security import sha256_digest
from app.modules.cor_screening.models import CorScreening
from app.modules.cor_screening.service import CorScreeningService
from .test_profile_change import _payload, _register, _superadmin, good_result, stub_screening
from .test_correction_evidence_retention import pending
from .test_student_correction_reads import login


def correction(db, user, registration, status="AWAITING_CONFIRMATION"):
    row = CorScreening(
        student_user_id=user.user_id, purpose="CORRECTION", status=status,
        format_template_version="test",
        submitted_at=registration.submitted_at + timedelta(seconds=1),
        verification_token_hash=sha256_digest("correction-only-secret"),
        verification_token_issued_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row


@pytest.mark.parametrize("status", ["PROCESSING", "AWAITING_CONFIRMATION", "NEEDS_RESUBMISSION", "FAILED", "PASSED"])
def test_newer_correction_does_not_replace_registration_reads_or_login(
    db_session, db_client, academic_references, monkeypatch, status,
):
    service, user, registration, profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    row = correction(db_session, user, registration, status)
    login(db_client, email=user.email)
    response = db_client.get("/api/v1/cor-screenings/me")
    assert response.status_code == 200
    assert response.json()["cor_screening_id"] == registration.cor_screening_id
    assert service.repository.latest_for_students([user.user_id]) == {user.user_id: registration}
    assert service.repository.list_all() == [registration]
    assert service.repository.list_all(status) == ([registration] if status == "PASSED" else [])
    assert service.repository.get(row.cor_screening_id) is row  # Exact evidence access stays possible.
    assert user.account_status == "ACTIVE"
    assert profile.section == "A"
    assert request.status == "PENDING"
    assert path.exists()


def test_correction_has_no_registration_fallback(db_session, academic_references, monkeypatch):
    service, user, registration, *_ = pending(db_session, academic_references, monkeypatch)
    registration.purpose = "CORRECTION"
    db_session.commit()
    assert service.latest_for_student(user) is None
    assert service.repository.find_latest_for_student(user.user_id, lock=True) is None
    assert service.repository.latest_for_students([user.user_id]) == {}
    assert service.repository.list_all() == []


@pytest.mark.parametrize("action", ["confirm", "request_edit", "reject", "resubmit", "issue_token"])
def test_resolved_registration_actions_deny_correction_before_mutation(
    db_session, academic_references, monkeypatch, action,
):
    service, user, registration, profile, request, evidence, path = pending(db_session, academic_references, monkeypatch)
    row = correction(db_session, user, registration)
    original_digest = row.verification_token_hash
    calls = {
        "confirm": lambda: service.confirm_resolved(user, row, None),
        "request_edit": lambda: service.request_edit_resolved(user, row, None),
        "reject": lambda: service.reject_resolved(user, row),
        "resubmit": lambda: service.resubmit_resolved(user, row, b"invalid", "cor.pdf"),
        "issue_token": lambda: service._issue_verification_token(row, datetime.now(timezone.utc)),
    }
    with pytest.raises(AppError) as caught:
        calls[action]()
    assert caught.value.code == ("INVALID_VERIFICATION_TOKEN" if action == "issue_token" else "SCREENING_NOT_CONFIRMABLE")
    assert not db_session.dirty
    assert row.status == "AWAITING_CONFIRMATION"
    assert row.verification_token_hash == original_digest
    assert registration.status == "PASSED"
    assert user.account_status == "ACTIVE"
    assert profile.section == "A"
    assert request.status == "PENDING"
    assert path.exists()


def test_correction_token_denied_even_with_valid_session(db_session, db_client, academic_references, monkeypatch):
    service, user, registration, *_ = pending(db_session, academic_references, monkeypatch)
    correction(db_session, user, registration)
    assert service.repository.find_by_token_hash(sha256_digest("correction-only-secret")) is None
    with pytest.raises(AppError) as caught:
        service.resolve_verification_token("correction-only-secret")
    assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
    login(db_client, email=user.email)
    csrf = db_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = db_client.post("/api/v1/cor-screenings/reject", headers={
        "X-CSRF-Token": csrf, "X-COR-Token": "correction-only-secret",
    })
    assert response.status_code == 401
    assert registration.status == "PASSED"


def test_token_purpose_rechecked_after_lock(db_session, academic_references, monkeypatch):
    service, user, registration, *_ = pending(db_session, academic_references, monkeypatch)
    row = correction(db_session, user, registration)
    # Simulate the initial nonlocking lookup having observed registration purpose.
    monkeypatch.setattr(service.repository, "find_by_token_hash", lambda digest: row)
    with pytest.raises(AppError) as caught:
        service.resolve_verification_token("correction-only-secret")
    assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
    assert row.verification_token_hash == sha256_digest("correction-only-secret")
    assert not db_session.dirty


@pytest.mark.parametrize("action", ["confirm", "reject", "resubmit", "recover"])
def test_session_registration_actions_select_registration_not_newer_correction(
    db_session, academic_references, monkeypatch, action,
):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, registration = _register(service)
    row = correction(db_session, user, registration)
    if action == "confirm":
        selected, activated, profile = service.confirm(user, _payload(*academic_references))
        assert selected is registration
        assert activated.account_status == "ACTIVE"
        assert profile.section == "A"
    elif action == "reject":
        assert service.reject(user) is registration
        assert registration.status == "NEEDS_RESUBMISSION"
    elif action == "resubmit":
        service.reject(user)
        selected, token = service.resubmit(user, b"%PDF-1.4 replacement", "cor.pdf")
        assert selected is registration
        assert token
        assert registration.status == "AWAITING_CONFIRMATION"
    else:
        _, _, selected = service.recover_student(_superadmin(db_session), user.user_id)
        assert selected is registration
        assert registration.failure_reason_code == "ADMIN_RECOVERY"
    assert row.status == "AWAITING_CONFIRMATION"
    assert row.verification_token_hash == sha256_digest("correction-only-secret")


def test_activation_primitive_denies_correction(db_session, academic_references, monkeypatch):
    service, user, registration, profile, *_ = pending(db_session, academic_references, monkeypatch)
    row = correction(db_session, user, registration)
    with pytest.raises(AppError) as caught:
        service._activate(user, row, **_payload(*academic_references).model_dump())
    assert caught.value.code == "SCREENING_NOT_CONFIRMABLE"
    assert not db_session.dirty
    assert profile.section == "A"
