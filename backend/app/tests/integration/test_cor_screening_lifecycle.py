"""Automated COR screening lifecycle against the disposable MySQL schema.

Skipped unless COUNSELCONNECT_TEST_DATABASE_URL is configured. External
document-processing binaries are stubbed, so these tests exercise the
service/DB flow, not the OCR engine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.core.security import sha256_digest
from app.modules.accounts.models import StudentProfile, User
from app.modules.cor_screening import screening as engine
from app.modules.cor_screening.models import CorScreening
from app.modules.cor_screening.schemas import ConfirmScreeningRequest
from app.modules.cor_screening.service import CorScreeningService


def stub_screening(monkeypatch, result):
    monkeypatch.setattr(engine, "ensure_dependencies", lambda settings: None)
    monkeypatch.setattr(engine, "screen_pdf", lambda path, settings: result)


def good_result(student_no="20231234-A", campus="Test Campus", course="Test Program"):
    return engine.ScreeningResult(
        fields=engine.ExtractedFields(
            student_no=student_no,
            name="Juan Dela Cruz",
            course=course,
            year="1",
            section="A",
            campus=campus,
            academic_period="2026-2027",
        ),
        method="text",
        format_score=1.0,
        extraction_confidence=1.0,
        missing=[],
        barcode_status=engine.BARCODE_DECODED,
        barcode_symbology="QRCode",
        barcode_payload=student_no,
        barcode_format_valid=True,
        barcode_student_number_match=True,
    )


def failed_result():
    return engine.ScreeningResult(
        fields=engine.ExtractedFields(student_no="20231234-A", name="Juan Dela Cruz"),
        method="text",
        format_score=1.0,
        extraction_confidence=1.0,
        missing=[],
        barcode_status=engine.BARCODE_NOT_FOUND,
    )


def test_registration_screen_confirm_activates_and_deletes_cor(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)

    user, screening, unmatched_campus, unmatched_program, _token = service.register_with_cor(
        "life@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    assert user.account_status == "PENDING_VERIFICATION"
    assert screening.status == "AWAITING_CONFIRMATION"
    assert unmatched_campus is None and unmatched_program is None

    file_row = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(file_row.storage_key))
    assert path.exists()

    data = ConfirmScreeningRequest(
        student_number="20231234-A",
        first_name="Juan",
        middle_name="Dela",
        last_name="Cruz",
        campus_id=campus_id,
        program_id=program_id,
        year_level=1,
        section="A",
        academic_period="2026-2027",
    )
    confirmed, activated, profile = service.confirm(user, data)
    assert activated.account_status == "ACTIVE"
    assert profile.student_number == "20231234-A"
    assert confirmed.status == "PASSED"
    assert confirmed.valid_until is not None
    assert not path.exists()
    assert service.repository.find_active_file(screening.cor_screening_id) is None


def test_resubmit_replaces_failed_screening(db_session, academic_references, monkeypatch):
    stub_screening(monkeypatch, failed_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, _ = service.register_with_cor(
        "resubmit@example.edu", "password1", b"%PDF-1.4 first", "cor.pdf"
    )
    assert screening.status == "NEEDS_RESUBMISSION"
    old = service.repository.find_active_file(screening.cor_screening_id)
    old_path = Path(service._storage_path(old.storage_key))

    stub_screening(monkeypatch, good_result())
    updated, _token = service.resubmit(user, b"%PDF-1.4 second", "cor.pdf")
    assert updated.status == "AWAITING_CONFIRMATION"
    active = service.repository.find_active_file(screening.cor_screening_id)
    assert active.storage_key != old.storage_key
    assert not old_path.exists()


def test_duplicate_student_number_is_rejected(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    owner = User(
        email="owner@example.edu",
        password_hash="unused",
        role_code="STUDENT",
        account_status="ACTIVE",
        first_name="Own",
        last_name="Er",
    )
    db_session.add(owner)
    db_session.flush()
    db_session.add(
        StudentProfile(
            user_id=owner.user_id,
            student_number="20231234-A",
            campus_id=campus_id,
            program_id=program_id,
            year_level=1,
            section="A",
        )
    )
    db_session.flush()

    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    with pytest.raises(AppError) as caught:
        service.register_with_cor("dup@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf")
    assert caught.value.code == "STUDENT_NUMBER_ALREADY_REGISTERED"


def test_expired_open_screening_is_failed_and_cor_deleted(
    db_session, academic_references, monkeypatch
):
    stub_screening(monkeypatch, failed_result())
    service = CorScreeningService(db_session)
    _, screening, _, _, _ = service.register_with_cor(
        "expire@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    file_row = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(file_row.storage_key))

    screening.submitted_at = datetime.now(timezone.utc) - timedelta(days=8)
    file_row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    service.cleanup_due_files()
    db_session.refresh(screening)
    assert screening.status == "FAILED"
    assert not path.exists()


def test_confirm_independently_denies_expired_evidence(
    db_session, academic_references, monkeypatch
):
    """Even if the cleanup worker is down, an aged screening cannot confirm."""
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, _ = service.register_with_cor(
        "aged@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    file_row = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(file_row.storage_key))
    screening.submitted_at = datetime.now(timezone.utc) - timedelta(days=8)
    # Aged evidence: the file TTL (same 7-day clock) has lapsed too, so the
    # confirm-time purge removes it even though the worker has not run.
    file_row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    data = ConfirmScreeningRequest(
        student_number="20231234-A",
        first_name="Juan",
        middle_name="Dela",
        last_name="Cruz",
        campus_id=campus_id,
        program_id=program_id,
        year_level=1,
        section="A",
    )
    with pytest.raises(AppError) as caught:
        service.confirm(user, data)
    assert caught.value.code == "SCREENING_EXPIRED"
    db_session.refresh(screening)
    assert screening.status == "FAILED"
    assert not path.exists()


def test_resubmit_after_expiry_gets_a_fresh_window(
    db_session, academic_references, monkeypatch
):
    stub_screening(monkeypatch, failed_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, _ = service.register_with_cor(
        "renew-window@example.edu", "password1", b"%PDF-1.4 first", "cor.pdf"
    )
    screening.submitted_at = datetime.now(timezone.utc) - timedelta(days=8)
    db_session.commit()

    stub_screening(monkeypatch, good_result())
    updated, _token = service.resubmit(user, b"%PDF-1.4 second", "cor.pdf")
    assert updated.status == "AWAITING_CONFIRMATION"
    active = service.repository.find_active_file(screening.cor_screening_id)
    assert active is not None
    assert service._storage_path(active.storage_key)  # retained, not deleted


def test_counselor_directory_lists_student_with_latest_screening(
    db_session, academic_references, monkeypatch
):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    student_user, screening, _, _, _ = service.register_with_cor(
        "directory@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    counselor = User(
        email="dir-counselor@example.edu",
        password_hash="x",
        role_code="COUNSELOR",
        account_status="ACTIVE",
        first_name="Cora",
        last_name="Reyes",
    )
    db_session.add(counselor)
    db_session.flush()

    rows = service.list_students(counselor, q="directory")
    assert len(rows) == 1
    user, _profile, latest = rows[0]
    assert user.user_id == student_user.user_id
    assert latest.cor_screening_id == screening.cor_screening_id

    assert len(service.list_students(counselor, q="directory")) == 1
    # A non-matching query filters the directory down to nothing.
    assert service.list_students(counselor, q="no-such-student") == []
    assert len(service.list_students(counselor, screening_status="AWAITING_CONFIRMATION")) == 1
    assert service.list_students(counselor, screening_status="PASSED") == []


def test_renewal_after_validity_starts_a_new_screening(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, _ = service.register_with_cor(
        "renew@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    data = ConfirmScreeningRequest(
        student_number="20231234-A",
        first_name="Juan",
        middle_name="Dela",
        last_name="Cruz",
        campus_id=campus_id,
        program_id=program_id,
        year_level=1,
        section="A",
        academic_period="2026-2027",
    )
    confirmed, activated, _ = service.confirm(user, data)
    first_id = confirmed.cor_screening_id
    confirmed.valid_until = datetime.now(timezone.utc).date() - timedelta(days=1)
    activated.account_status = "VERIFICATION_EXPIRED"
    db_session.commit()

    stub_screening(monkeypatch, good_result())
    renewed, _token = service.resubmit(user, b"%PDF-1.4 renew", "cor.pdf")
    assert renewed.cor_screening_id != first_id
    assert renewed.status == "AWAITING_CONFIRMATION"


# --------------------------------------------------- one-time verification token


def test_register_returns_only_a_hashed_token_and_token_confirms(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, token = service.register_with_cor(
        "token@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    assert token
    assert screening.verification_token_hash == sha256_digest(token)
    assert screening.verification_token_issued_at is not None
    assert token not in str(screening.verification_token_hash)

    # No session: the token alone resolves the student + screening.
    student, resolved = service.resolve_verification_token(token)
    assert student.user_id == user.user_id
    assert resolved.cor_screening_id == screening.cor_screening_id

    data = ConfirmScreeningRequest(
        student_number="20231234-A",
        first_name="Juan",
        middle_name="Dela",
        last_name="Cruz",
        campus_id=campus_id,
        program_id=program_id,
        year_level=1,
        section="A",
        academic_period="2026-2027",
    )
    confirmed, activated, _profile = service.confirm_resolved(student, resolved, data)
    assert activated.account_status == "ACTIVE"
    assert confirmed.status == "PASSED"
    # Activation destroys the token.
    assert confirmed.verification_token_hash is None
    with pytest.raises(AppError) as caught:
        service.resolve_verification_token(token)
    assert caught.value.code == "INVALID_VERIFICATION_TOKEN"


def test_resubmit_rotates_the_token(db_session, academic_references, monkeypatch):
    stub_screening(monkeypatch, failed_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, first_token = service.register_with_cor(
        "rotate@example.edu", "password1", b"%PDF-1.4 first", "cor.pdf"
    )
    assert screening.status == "NEEDS_RESUBMISSION"

    stub_screening(monkeypatch, good_result())
    updated, second_token = service.resubmit_resolved(
        user, screening, b"%PDF-1.4 second", "cor.pdf"
    )
    assert second_token and second_token != first_token
    assert updated.status == "AWAITING_CONFIRMATION"
    # The previous token is dead; the rotated one resolves.
    with pytest.raises(AppError) as caught:
        service.resolve_verification_token(first_token)
    assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
    student, resolved = service.resolve_verification_token(second_token)
    assert resolved.cor_screening_id == updated.cor_screening_id


def test_reject_keeps_the_token_valid_for_reupload(
    db_session, academic_references, monkeypatch
):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening, _, _, token = service.register_with_cor(
        "reject-token@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    student, resolved = service.resolve_verification_token(token)
    rejected = service.reject_resolved(student, resolved)
    assert rejected.status == "NEEDS_RESUBMISSION"
    # Same token still authorizes the follow-up re-upload.
    _student, still_valid = service.resolve_verification_token(token)
    assert still_valid.cor_screening_id == screening.cor_screening_id


def test_unknown_or_empty_token_fails_closed(db_session, academic_references, monkeypatch):
    service = CorScreeningService(db_session)
    for bad in (None, "", "   ", "not-a-real-token"):
        with pytest.raises(AppError) as caught:
            service.resolve_verification_token(bad)
        assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
        assert caught.value.status_code == 401


def test_expired_token_is_rejected_and_retired(
    db_session, academic_references, monkeypatch
):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    _user, screening, _, _, token = service.register_with_cor(
        "expired-token@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    screening.submitted_at = datetime.now(timezone.utc) - timedelta(days=8)
    db_session.commit()

    with pytest.raises(AppError) as caught:
        service.resolve_verification_token(token)
    assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
    db_session.refresh(screening)
    assert screening.status == "FAILED"
    assert screening.verification_token_hash is None


# ----------------------------------------- failure isolation / reject account


def technical_failed_result():
    """A decoder/processing state we cannot attribute to the document."""
    return engine.ScreeningResult(
        fields=engine.ExtractedFields(student_no="20231234-A", name="Juan Dela Cruz"),
        method="text",
        format_score=1.0,
        extraction_confidence=1.0,
        missing=[],
        barcode_status=engine.BARCODE_NOT_PROCESSED,
    )


def test_technical_failure_creates_no_account(db_session, academic_references, monkeypatch):
    stub_screening(monkeypatch, technical_failed_result())
    service = CorScreeningService(db_session)

    with pytest.raises(AppError) as caught:
        service.register_with_cor(
            "noaccount@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
        )
    assert caught.value.code == "SCREENING_FAILED"
    assert (
        db_session.scalars(select(User).where(User.email == "noaccount@example.edu")).first()
        is None
    )

    # The same email can register once the screener recovers.
    stub_screening(monkeypatch, good_result())
    user, screening, _, _, _ = service.register_with_cor(
        "noaccount@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    assert user.account_status == "PENDING_VERIFICATION"


def test_reject_account_deletes_everything_and_frees_identity(
    db_session, academic_references, monkeypatch
):
    # Mirror the production session (autoflush=False) so the audit-insert
    # ordering before the deletes is actually exercised.
    db_session.autoflush = False
    stub_screening(monkeypatch, failed_result())  # NEEDS_RESUBMISSION -> account created
    service = CorScreeningService(db_session)
    user, screening, _, _, _ = service.register_with_cor(
        "rejectme@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    file_row = service.repository.find_active_file(screening.cor_screening_id)
    path = Path(service._storage_path(file_row.storage_key))
    assert path.exists()
    user_id, screening_id = user.user_id, screening.cor_screening_id

    service.reject_account(user)

    assert db_session.scalars(select(User).where(User.user_id == user_id)).first() is None
    assert db_session.scalars(
        select(CorScreening).where(CorScreening.cor_screening_id == screening_id)
    ).first() is None
    assert not path.exists()

    # Email is free again for a fresh registration.
    user2, _screening2, _, _, _ = service.register_with_cor(
        "rejectme@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    assert user2.email == "rejectme@example.edu"


def test_reject_account_denied_when_active(db_session, academic_references, monkeypatch):
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening, _, _, _ = service.register_with_cor(
        "activereject@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    user.account_status = "ACTIVE"
    db_session.commit()

    with pytest.raises(AppError) as caught:
        service.reject_account(user)
    assert caught.value.code == "ACCOUNT_NOT_REJECTABLE"
