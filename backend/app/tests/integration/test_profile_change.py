"""Student profile-edit request lifecycle (ADR-032) against the MySQL schema.

Skipped unless COUNSELCONNECT_TEST_DATABASE_URL is configured. OCR tooling is
stubbed, so these exercise the service/DB flow.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.cor_screening import screening as engine
from app.modules.cor_screening.schemas import RequestEditRequest
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.service import ProfileChangeService


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


def _register(service, email="edit@example.edu"):
    user, screening, _campus, _program, _token = service.register_with_cor(
        email, "password1", b"%PDF-1.4 test", "cor.pdf"
    )
    return user, screening


def _payload(campus_id, program_id, **overrides):
    values = {
        "student_number": "20231234-A",
        "first_name": "Juan",
        "middle_name": "Dela",
        "last_name": "Cruz",
        "campus_id": campus_id,
        "program_id": program_id,
        "year_level": 1,
        "section": "A",
        "academic_period": "2026-2027",
    }
    values.update(overrides)
    return RequestEditRequest(**values)


def _superadmin(db_session) -> User:
    user = User(
        email="edit-super@example.edu",
        password_hash=hash_password("super-pass-1"),
        role_code="SUPERADMIN",
        account_status="ACTIVE",
        first_name="Super",
        last_name="Admin",
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_request_edit_activates_with_cor_values_and_queues_pending(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service)

    scr, activated, profile, change_request = service.request_edit(
        user, _payload(campus_id, program_id, last_name="Reyes", year_level=2, section="B")
    )

    assert activated.account_status == "ACTIVE"
    assert scr.status == "PASSED"
    assert change_request is not None and change_request.status == "PENDING"
    assert change_request.requested_last_name == "Reyes"
    assert change_request.requested_year_level == 2
    assert change_request.requested_section == "B"
    # Activation used the COR-verified values, not the requested ones.
    assert activated.last_name == "Cruz"
    assert profile.year_level == 1
    assert profile.section == "A"


def test_request_edit_without_a_difference_is_a_plain_confirmation(
    db_session, academic_references, monkeypatch
):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service, email="edit-unchanged@example.edu")

    _scr, activated, _profile, change_request = service.request_edit(
        user, _payload(campus_id, program_id)
    )
    assert activated.account_status == "ACTIVE"
    assert change_request is None


def test_request_edit_rejects_excluded_fields(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service, email="edit-excluded@example.edu")

    with pytest.raises(AppError) as academic:
        service.request_edit(user, _payload(campus_id, program_id, academic_period="2027-2028"))
    assert academic.value.code == "FIELD_NOT_EDITABLE"

    with pytest.raises(AppError) as campus:
        service.request_edit(user, _payload(campus_id + 1, program_id))
    assert campus.value.code == "FIELD_NOT_EDITABLE"

    with pytest.raises(AppError) as number:
        service.request_edit(user, _payload(campus_id, program_id, student_number="20239999-B"))
    assert number.value.code == "STUDENT_NUMBER_MISMATCH"


def test_create_pending_rejects_a_second_pending(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service, email="edit-second@example.edu")
    _scr, _activated, _profile, _first = service.request_edit(
        user, _payload(campus_id, program_id, section="B")
    )
    reviews = ProfileChangeService(db_session)

    with pytest.raises(AppError) as caught:
        reviews.create_pending(
            user,
            screening.cor_screening_id,
            first_name="Ana",
            middle_name="Dela",
            last_name="Cruz",
            year_level=1,
            section="B",
        )
    assert caught.value.code == "CHANGE_REQUEST_PENDING"


def test_create_pending_rejects_blank_values(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service, email="edit-blank@example.edu")
    reviews = ProfileChangeService(db_session)

    with pytest.raises(AppError) as blank:
        reviews.create_pending(
            user,
            screening.cor_screening_id,
            first_name="Ana",
            middle_name=None,
            last_name="   ",
            year_level=1,
            section="A",
        )
    assert blank.value.code == "INVALID_PROFILE_EDIT"


def test_superadmin_approve_applies_edits(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service, email="edit-approve@example.edu")
    _scr, _activated, profile, change_request = service.request_edit(
        user, _payload(campus_id, program_id, last_name="Reyes", year_level=3, section="C")
    )
    superadmin = _superadmin(db_session)
    reviews = ProfileChangeService(db_session)

    # Only a Superadmin may decide.
    with pytest.raises(AppError) as forbidden:
        reviews.approve(user, change_request.change_request_id)
    assert forbidden.value.code == "FORBIDDEN_ROLE"

    approved = reviews.approve(superadmin, change_request.change_request_id)
    assert approved.status == "APPROVED"
    db_session.refresh(user)
    db_session.refresh(profile)
    assert user.last_name == "Reyes"
    assert profile.year_level == 3
    assert profile.section == "C"

    # Deciding a non-pending request is rejected.
    with pytest.raises(AppError) as decided:
        reviews.approve(superadmin, change_request.change_request_id)
    assert decided.value.code == "CHANGE_REQUEST_NOT_PENDING"


def test_superadmin_reject_keeps_original_values(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service, email="edit-reject@example.edu")
    _scr, _activated, profile, change_request = service.request_edit(
        user, _payload(campus_id, program_id, last_name="Reyes")
    )
    superadmin = _superadmin(db_session)
    reviews = ProfileChangeService(db_session)

    rejected = reviews.reject(superadmin, change_request.change_request_id, "Blurry COR")
    assert rejected.status == "REJECTED"
    assert rejected.decision_reason == "Blurry COR"
    db_session.refresh(user)
    db_session.refresh(profile)
    assert user.last_name == "Cruz"
    assert profile.section == "A"


def test_supersede_pending_marks_rejected(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service, email="edit-supersede@example.edu")
    _scr, _activated, _profile, change_request = service.request_edit(
        user, _payload(campus_id, program_id, section="B")
    )
    reviews = ProfileChangeService(db_session)

    row = reviews.supersede_pending(user.user_id)
    assert row is not None
    assert row.change_request_id == change_request.change_request_id
    assert row.status == "REJECTED"
    assert row.decision_reason == "SUPERSEDED_BY_NEW_COR"


def test_resubmit_supersedes_a_pending_request(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, screening = _register(service, email="edit-supersede-resubmit@example.edu")
    _scr, _activated, _profile, change_request = service.request_edit(
        user, _payload(campus_id, program_id, section="B")
    )
    # Expire the pass so a resubmit takes the renewal branch.
    screening.valid_until = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    user.account_status = "VERIFICATION_EXPIRED"
    db_session.commit()

    service.resubmit(user, b"%PDF-1.4 renew", "cor.pdf")
    db_session.refresh(change_request)
    assert change_request.status == "REJECTED"
    assert change_request.decision_reason == "SUPERSEDED_BY_NEW_COR"


def test_list_requests_requires_superadmin(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    user, _screening = _register(service, email="edit-list@example.edu")
    service.request_edit(user, _payload(campus_id, program_id, last_name="Reyes"))
    reviews = ProfileChangeService(db_session)

    with pytest.raises(AppError) as forbidden:
        reviews.list_requests(user)
    assert forbidden.value.code == "FORBIDDEN_ROLE"

    superadmin = _superadmin(db_session)
    items = reviews.list_requests(superadmin)
    assert len(items) == 1
    assert items[0].change_request.status == "PENDING"
    assert items[0].current_last_name == "Cruz"
    assert items[0].change_request.requested_last_name == "Reyes"
