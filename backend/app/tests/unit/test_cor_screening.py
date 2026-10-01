"""Automated COR screening unit tests (no database, no external binaries)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AppError
from app.core.security import sha256_digest
from app.modules.cor_screening import screening as engine
from app.modules.cor_screening.models import CorScreening
from app.modules.cor_screening.service import CorScreeningService
from app.modules.cor_screening.schemas import ConfirmScreeningRequest


def make_result(**overrides):
    defaults = dict(
        fields=engine.ExtractedFields(
            student_no="20231234-A",
            name="Juan Dela Cruz",
            course="BSIT",
            year="1",
            section="A",
            campus="Main",
            academic_period="2026-2027",
        ),
        method="text",
        format_score=1.0,
        extraction_confidence=1.0,
        missing=[],
        barcode_status=engine.BARCODE_DECODED,
        barcode_symbology="QRCode",
        barcode_payload="20231234-A",
        barcode_format_valid=True,
        barcode_student_number_match=True,
    )
    defaults.update(overrides)
    return engine.ScreeningResult(**defaults)


def make_service():
    service = CorScreeningService(Session())
    service.accounts = Mock()
    service.repository = Mock()
    service.accounts.list_active_campuses.return_value = []
    service.accounts.list_active_programs.return_value = []
    return service


def make_screening():
    return CorScreening(
        student_user_id=1,
        status="PROCESSING",
        format_template_version="test",
        submitted_at=datetime.now(timezone.utc),
    )


# --------------------------------------------------------------- outcome matrix


def test_clean_screening_awaits_confirmation():
    status, failure = engine.derive_outcome(make_result(), get_settings())
    assert status == "AWAITING_CONFIRMATION"
    assert failure is None


def test_unreadable_document_requests_resubmission():
    status, failure = engine.derive_outcome(make_result(method="none"), get_settings())
    assert (status, failure) == ("NEEDS_RESUBMISSION", "UNREADABLE_DOCUMENT")


@pytest.mark.parametrize(
    "barcode_status,code",
    [
        (engine.BARCODE_NOT_FOUND, "BARCODE_NOT_FOUND"),
        (engine.BARCODE_UNREADABLE, "BARCODE_UNREADABLE"),
        (engine.BARCODE_INVALID_FORMAT, "BARCODE_INVALID_FORMAT"),
        (engine.BARCODE_MISMATCH, "BARCODE_MISMATCH"),
    ],
)
def test_barcode_failures_request_resubmission(barcode_status, code):
    status, failure = engine.derive_outcome(
        make_result(barcode_status=barcode_status), get_settings()
    )
    assert (status, failure) == ("NEEDS_RESUBMISSION", code)


def test_technical_barcode_failure_is_failed():
    result = make_result(barcode_status=engine.BARCODE_NOT_PROCESSED)
    status, failure = engine.derive_outcome(result, get_settings())
    assert (status, failure) == ("FAILED", "TECHNICAL_ERROR")


def test_low_format_requests_resubmission():
    status, failure = engine.derive_outcome(make_result(format_score=0.10), get_settings())
    assert (status, failure) == ("NEEDS_RESUBMISSION", "LOW_FORMAT_SCORE")


def test_missing_required_fields_requests_resubmission():
    result = make_result(extraction_confidence=0.4, missing=["student_no", "name", "course"])
    status, failure = engine.derive_outcome(result, get_settings())
    assert (status, failure) == ("NEEDS_RESUBMISSION", "MISSING_REQUIRED_FIELDS")


def test_awaiting_requires_every_required_field():
    # Verified fields are read-only, so a partial extraction cannot be confirmed.
    result = make_result(extraction_confidence=0.8, missing=["section"])
    status, failure = engine.derive_outcome(result, get_settings())
    assert (status, failure) == ("NEEDS_RESUBMISSION", "MISSING_REQUIRED_FIELDS")


def test_student_number_pattern_is_strict():
    assert engine.STUDENT_NO_RE.match("20231234-A")
    assert not engine.STUDENT_NO_RE.match("2026-00001")
    assert not engine.STUDENT_NO_RE.match("2023123-A")


# --------------------------------------------------- persistence / privacy rules


def test_barcode_payload_is_hashed_never_stored_or_logged():
    service = make_service()
    screening = make_screening()
    result = make_result()
    service._apply_result(screening, result, "20231234-A", datetime.now(timezone.utc))

    assert screening.barcode_payload_hash == hashlib.sha256(b"20231234-A").digest()
    # No attribute ever holds the raw payload.
    assert not hasattr(screening, "barcode_payload")
    stored = str(screening.validation_results_json)
    assert "20231234-A" not in stored
    assert set(screening.validation_results_json) == {
        "method",
        "format_score",
        "extraction_confidence",
        "missing_fields",
        "barcode_status",
    }


def test_unmatched_reference_names_are_returned_not_created():
    service = make_service()
    screening = make_screening()
    unmatched_campus, unmatched_program = service._apply_result(
        screening, make_result(), "20231234-A", datetime.now(timezone.utc)
    )
    assert unmatched_campus == "Main"
    assert unmatched_program == "BSIT"
    service.accounts.list_active_campuses.assert_called()
    service.accounts.list_active_programs.assert_called()


def test_campus_and_program_match_existing_active_rows():
    service = make_service()
    service.accounts.list_active_campuses.return_value = [
        SimpleNamespace(campus_id=7, campus_name="Main Campus")
    ]
    service.accounts.list_active_programs.return_value = [
        SimpleNamespace(program_id=9, program_name="BS Information Technology", program_code="BSIT")
    ]
    screening = make_screening()
    result = make_result(
        fields=engine.ExtractedFields(
            student_no="20231234-A",
            name="Juan Dela Cruz",
            course="BSIT",
            year="1",
            section="A",
            campus="Main",
            academic_period="2026-2027",
        )
    )
    unmatched_campus, unmatched_program = service._apply_result(
        screening, result, "20231234-A", datetime.now(timezone.utc)
    )
    assert screening.extracted_campus_id == 7
    assert screening.extracted_program_id == 9
    assert unmatched_campus is None and unmatched_program is None


# ------------------------------------------------------------- fail-closed gates


def test_registration_disabled_fails_closed(monkeypatch):
    monkeypatch.setenv("COUNSELCONNECT_COR_SCREENING_ENABLED", "false")
    get_settings.cache_clear()
    try:
        service = make_service()
        with pytest.raises(AppError) as caught:
            service.register_with_cor("a@example.edu", "password1", b"%PDF-x", "cor.pdf")
        assert caught.value.code == "REGISTRATION_DISABLED"
    finally:
        get_settings.cache_clear()


def test_missing_screening_dependencies_fail_closed(monkeypatch):
    monkeypatch.setattr(
        engine, "ensure_dependencies", Mock(side_effect=engine.ScreeningUnavailableError("no tools"))
    )
    service = make_service()
    with pytest.raises(AppError) as caught:
        service.register_with_cor("a@example.edu", "password1", b"%PDF-x", "cor.pdf")
    assert caught.value.code == "SCREENING_UNAVAILABLE"


def test_invalid_upload_is_rejected_before_any_write():
    service = make_service()
    with pytest.raises(AppError) as caught:
        service._validate_pdf(b"not-a-pdf", "cor.pdf", 10)
    assert caught.value.code == "COR_INVALID_PDF"
    with pytest.raises(AppError) as caught:
        service._validate_pdf(b"%PDF-x", "cor.txt", 10)
    assert caught.value.code == "COR_MUST_BE_PDF"
    with pytest.raises(AppError) as caught:
        service._validate_pdf(b"%PDF-x", "cor.pdf", 0)
    assert caught.value.code == "COR_TOO_LARGE"


def test_private_storage_rejects_path_escape(tmp_path):
    service = CorScreeningService(Session())
    outside = tmp_path / "keep.pdf"
    outside.write_bytes(b"private-test")
    assert service._delete_cor_bytes(str(outside)) is False
    assert outside.read_bytes() == b"private-test"


# ----------------------------------------------------------------- authorization


def test_non_student_cannot_view_screening():
    service = make_service()
    with pytest.raises(AppError) as caught:
        service.latest_for_student(SimpleNamespace(role_code="COUNSELOR", user_id=1))
    assert caught.value.code == "FORBIDDEN_ROLE"


def test_inactive_counselor_cannot_list_screenings():
    service = make_service()
    with pytest.raises(AppError) as caught:
        service.list_for_counselor(SimpleNamespace(role_code="COUNSELOR", account_status="PENDING_VERIFICATION"))
    assert caught.value.code == "FORBIDDEN_ROLE"


def test_non_counselor_cannot_list_student_directory():
    service = make_service()
    with pytest.raises(AppError) as caught:
        service.list_students(
            SimpleNamespace(role_code="STUDENT", account_status="ACTIVE", user_id=1)
        )
    assert caught.value.code == "FORBIDDEN_ROLE"


def test_inactive_counselor_cannot_list_student_directory():
    service = make_service()
    with pytest.raises(AppError) as caught:
        service.list_students(
            SimpleNamespace(role_code="COUNSELOR", account_status="VERIFICATION_EXPIRED")
        )
    assert caught.value.code == "FORBIDDEN_ROLE"


def test_directory_attaches_latest_screening_and_filters_by_status():
    service = make_service()
    counselor = SimpleNamespace(role_code="COUNSELOR", account_status="ACTIVE", user_id=9)
    user = SimpleNamespace(user_id=1, email="a@example.edu")
    profile = SimpleNamespace(student_number="20231234-A")
    screening = SimpleNamespace(status="PASSED")
    service.accounts.list_students.return_value = [(user, profile)]
    service.repository.latest_for_students.return_value = {1: screening}

    rows = service.list_students(counselor)
    assert rows == [(user, profile, screening)]
    assert service.list_students(counselor, screening_status="FAILED") == []
    assert service.list_students(counselor, screening_status="PASSED") == [(user, profile, screening)]


def test_confirm_rejects_invalid_student_number():
    service = CorScreeningService(Session())
    service.accounts = Mock()
    service.accounts.lock_user.return_value = SimpleNamespace(user_id=1, role_code="STUDENT")
    service.repository = Mock()
    service.repository.find_latest_for_student.return_value = SimpleNamespace(
        status="AWAITING_CONFIRMATION", submitted_at=datetime.now(timezone.utc)
    )
    data = ConfirmScreeningRequest(
        student_number="2026-00001",
        first_name="Juan",
        last_name="Dela Cruz",
        campus_id=1,
        program_id=1,
        year_level=1,
        section="A",
    )
    with pytest.raises(AppError) as caught:
        service.confirm(SimpleNamespace(user_id=1), data)
    assert caught.value.code == "INVALID_STUDENT_NUMBER"


def test_confirm_rejects_number_that_differs_from_barcode_value():
    service = CorScreeningService(Session())
    service.accounts = Mock()
    service.accounts.lock_user.return_value = SimpleNamespace(user_id=1, role_code="STUDENT")
    service.accounts.find_student_profile_by_number.return_value = None
    service.repository = Mock()
    service.repository.find_latest_for_student.return_value = SimpleNamespace(
        status="AWAITING_CONFIRMATION",
        submitted_at=datetime.now(timezone.utc),
        extracted_student_number="20231234-A",
    )
    data = ConfirmScreeningRequest(
        student_number="20231235-B",
        first_name="Juan",
        last_name="Dela Cruz",
        campus_id=1,
        program_id=1,
        year_level=1,
        section="A",
    )
    with pytest.raises(AppError) as caught:
        service.confirm(SimpleNamespace(user_id=1), data)
    assert caught.value.code == "STUDENT_NUMBER_MISMATCH"


def test_confirm_rejects_an_edited_verified_field():
    service = CorScreeningService(Session())
    service.accounts = Mock()
    service.accounts.lock_user.return_value = SimpleNamespace(user_id=1, role_code="STUDENT")
    service.accounts.find_student_profile_by_number.return_value = None
    service.repository = Mock()
    service.repository.find_latest_for_student.return_value = SimpleNamespace(
        status="AWAITING_CONFIRMATION",
        submitted_at=datetime.now(timezone.utc),
        extracted_student_number="20231234-A",
        extracted_first_name="Ana",
        extracted_middle_name=None,
        extracted_last_name="Santos",
        extracted_campus_id=1,
        extracted_program_id=1,
        extracted_year_level=1,
        extracted_section="A",
        extracted_academic_period=None,
    )
    data = ConfirmScreeningRequest(
        student_number="20231234-A",
        first_name="Ana",
        last_name="Edited",
        campus_id=1,
        program_id=1,
        year_level=1,
        section="A",
    )
    with pytest.raises(AppError) as caught:
        service.confirm(SimpleNamespace(user_id=1), data)
    assert caught.value.code == "FIELD_MISMATCH"


def test_reject_requires_awaiting_confirmation():
    service = CorScreeningService(Session())
    service.accounts = Mock()
    service.accounts.lock_user.return_value = SimpleNamespace(user_id=1, role_code="STUDENT")
    service.repository = Mock()
    service.repository.find_latest_for_student.return_value = SimpleNamespace(status="PASSED")
    with pytest.raises(AppError) as caught:
        service.reject(SimpleNamespace(user_id=1))
    assert caught.value.code == "SCREENING_NOT_CONFIRMABLE"


def test_reject_marks_needs_resubmission_by_student():
    service = CorScreeningService(Session())
    service.accounts = Mock()
    service.accounts.lock_user.return_value = SimpleNamespace(user_id=1, role_code="STUDENT")
    service.repository = Mock()
    service.repository.find_latest_for_student.return_value = SimpleNamespace(
        status="AWAITING_CONFIRMATION",
        failure_reason_code=None,
        processed_at=None,
        cor_screening_id=5,
    )
    result = service.reject(SimpleNamespace(user_id=1))
    assert result.status == "NEEDS_RESUBMISSION"
    assert result.failure_reason_code == "REJECTED_BY_STUDENT"


def test_recover_requires_superadmin():
    service = make_service()
    with pytest.raises(AppError) as caught:
        service.recover_student(
            SimpleNamespace(role_code="COUNSELOR", account_status="ACTIVE", user_id=1), 5
        )
    assert caught.value.code == "FORBIDDEN_ROLE"


def test_recover_rejects_active_account():
    service = make_service()
    service.accounts.lock_user.return_value = SimpleNamespace(
        user_id=5, role_code="STUDENT", account_status="ACTIVE"
    )
    with pytest.raises(AppError) as caught:
        service.recover_student(
            SimpleNamespace(role_code="SUPERADMIN", account_status="ACTIVE", user_id=1), 5
        )
    assert caught.value.code == "NOT_RECOVERABLE"


def test_recover_resets_a_stuck_student():
    service = make_service()
    service.accounts.lock_user.return_value = SimpleNamespace(
        user_id=5, role_code="STUDENT", account_status="PENDING_VERIFICATION"
    )
    screening = SimpleNamespace(status="PROCESSING", failure_reason_code=None, processed_at=None)
    service.repository.find_latest_for_student.return_value = screening
    user, _profile, latest = service.recover_student(
        SimpleNamespace(role_code="SUPERADMIN", account_status="ACTIVE", user_id=1), 5
    )
    assert user.account_status == "PENDING_VERIFICATION"
    assert latest.status == "NEEDS_RESUBMISSION"
    assert latest.failure_reason_code == "ADMIN_RECOVERY"


def test_directory_allows_superadmin_read():
    service = make_service()
    service.accounts.list_students.return_value = []
    service.repository.latest_for_students.return_value = {}
    assert service.list_students(
        SimpleNamespace(role_code="SUPERADMIN", account_status="ACTIVE", user_id=1)
    ) == []


# ------------------------------------------------- one-time verification token


def test_issue_verification_token_stores_only_the_digest():
    service = CorScreeningService(Session())
    screening = make_screening()
    raw = service._issue_verification_token(screening, datetime.now(timezone.utc))
    assert raw
    assert screening.verification_token_hash == sha256_digest(raw)
    assert screening.verification_token_issued_at is not None
    assert raw not in str(screening.verification_token_hash)

    service._clear_verification_token(screening)
    assert screening.verification_token_hash is None
    assert screening.verification_token_issued_at is None


def test_resolve_verification_token_rejects_missing_value():
    service = make_service()
    for bad in (None, "", "   "):
        with pytest.raises(AppError) as caught:
            service.resolve_verification_token(bad)
        assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
        assert caught.value.status_code == 401


def test_resolve_verification_token_rejects_unknown_digest():
    service = make_service()
    service.repository.find_by_token_hash.return_value = None
    with pytest.raises(AppError) as caught:
        service.resolve_verification_token("unknown-token")
    assert caught.value.code == "INVALID_VERIFICATION_TOKEN"
    assert caught.value.status_code == 401
