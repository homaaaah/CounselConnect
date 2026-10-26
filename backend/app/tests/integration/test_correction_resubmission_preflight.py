"""Locked resubmission prerequisites without uploading or creating versions."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_evidence_retention import pending
from .test_profile_change import _superadmin


@pytest.fixture
def returned_context(db_session, academic_references, monkeypatch):
    values = pending(db_session, academic_references, monkeypatch)
    service, user, enrolled, profile, row, file, path = values
    ProfileChangeService(db_session).return_request(
        _superadmin(db_session), row.change_request_id, "Recheck section.", submission_version=1,
    )
    return values


def prepare(db, values, **kwargs):
    _, user, _, _, row, _, _ = values
    return ProfileChangeService(db).prepare_resubmission(user, row.change_request_id, **kwargs)


@pytest.mark.parametrize("legacy", [False, True])
def test_preflight_preserves_history_and_uses_current_baseline(db_session, returned_context, legacy, monkeypatch):
    _, user, enrolled, profile, row, file, path = returned_context
    if legacy:
        row.submission_version = None
        row.status = "REJECTED"
    profile.section = "CURRENT"
    db_session.commit()
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    screens = db_session.scalar(select(func.count()).select_from(CorScreening))
    monkeypatch.setattr(db_session, "commit", lambda: pytest.fail("preflight must not commit"))
    result = prepare(db_session, returned_context, submission_version=row.submission_version)
    assert result == (row, user, profile, enrolled)
    assert result[2].section == "CURRENT"
    assert row.requested_section == "B" and row.registered_values_json["section"] == "A"
    assert not path.exists()
    assert not db_session.new and not db_session.dirty
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == count
    assert db_session.scalar(select(func.count()).select_from(CorScreening)) == screens


@pytest.mark.parametrize("version", [None, 2, 0, -1, True, "1", 1.0])
def test_preflight_requires_exact_explicit_strict_version(db_session, returned_context, version):
    with pytest.raises(AppError) as caught:
        prepare(db_session, returned_context, submission_version=version)
    assert caught.value.code == ("CHANGE_REQUEST_VERSION_CONFLICT" if version is None or version == 2
                                else "VALIDATION_ERROR")


def test_preflight_requires_version_argument(db_session, returned_context):
    with pytest.raises(TypeError):
        prepare(db_session, returned_context)


@pytest.mark.parametrize("case", ["pending", "approved", "expired", "deactivated", "pending_account",
                                  "missing_profile", "number", "inactive_campus", "inactive_program"])
def test_preflight_denies_ineligible_context(db_session, returned_context, case):
    _, user, enrolled, profile, row, file, path = returned_context
    accounts = ProfileChangeService(db_session).accounts
    if case == "pending":
        row.status = "PENDING"
    elif case == "approved":
        row.status = "APPROVED"
    elif case == "expired":
        enrolled.valid_until -= timedelta(days=400)
    elif case == "deactivated":
        user.is_deactivated = True
    elif case == "pending_account":
        user.account_status = "PENDING_VERIFICATION"
    elif case == "missing_profile":
        db_session.delete(profile)
    elif case == "number":
        profile.student_number = "20239999-B"
    elif case == "inactive_campus":
        accounts.find_campus(profile.campus_id).is_active = False
    else:
        accounts.find_program(profile.program_id).is_active = False
    db_session.commit()
    with pytest.raises(AppError) as caught:
        prepare(db_session, returned_context, submission_version=1)
    assert caught.value.code == ("ACCOUNT_DEACTIVATED" if case == "deactivated" else "CORRECTION_RESUBMISSION_NOT_ALLOWED")
    assert not db_session.new and not db_session.dirty


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_STAFF", "SUPERADMIN"])
def test_preflight_denies_staff_before_lookup(db_session, returned_context, role, monkeypatch):
    service = ProfileChangeService(db_session)
    monkeypatch.setattr(service.repository, "get_for_student", lambda *args: pytest.fail("must not query requests"))
    with pytest.raises(AppError) as caught:
        service.prepare_resubmission(SimpleNamespace(role_code=role, is_deactivated=False), 1, submission_version=1)
    assert caught.value.code == "FORBIDDEN_ROLE"


def test_foreign_and_missing_request_have_same_not_found(db_session, returned_context):
    _, user, _, _, row, _, _ = returned_context
    service = ProfileChangeService(db_session)
    foreign_id = row.change_request_id
    other = User(email="other-resubmit@example.edu", password_hash="unused", role_code="STUDENT",
                 account_status="ACTIVE", first_name="Other", last_name="Student")
    db_session.add(other)
    db_session.commit()
    for request_id in (foreign_id, 999999):
        with pytest.raises(AppError) as caught:
            service.prepare_resubmission(other, request_id, submission_version=1)
        assert caught.value.code == "CHANGE_REQUEST_NOT_FOUND"


def test_preflight_refuses_old_predecessor_with_successor(db_session, returned_context):
    _, user, enrolled, profile, row, _, _ = returned_context
    child = ProfileChangeRequest(student_user_id=user.user_id, cor_screening_id=enrolled.cor_screening_id,
        requested_first_name="Juan", requested_last_name="Cruz", requested_year_level=1, requested_section="B",
        status="RETURNED", submission_version=2, previous_change_request_id=row.change_request_id,
        root_change_request_id=row.change_request_id)
    db_session.add(child)
    db_session.commit()
    with pytest.raises(AppError) as caught:
        prepare(db_session, returned_context, submission_version=1)
    assert caught.value.code == "CHANGE_REQUEST_VERSION_CONFLICT"
    selected, *_ = ProfileChangeService(db_session).prepare_resubmission(user, child.change_request_id, submission_version=2)
    assert selected is child


def test_preflight_refuses_another_pending_request(db_session, returned_context):
    _, user, enrolled, profile, row, _, _ = returned_context
    db_session.add(ProfileChangeRequest(student_user_id=user.user_id, cor_screening_id=enrolled.cor_screening_id,
        requested_first_name="Juan", requested_last_name="Cruz", requested_year_level=1, requested_section="B",
        status="PENDING", submission_version=1))
    db_session.commit()
    with pytest.raises(AppError) as caught:
        prepare(db_session, returned_context, submission_version=1)
    assert caught.value.code == "CHANGE_REQUEST_PENDING"


def test_preflight_rechecks_locked_actor(db_session, returned_context):
    _, user, _, _, row, _, _ = returned_context
    stale = SimpleNamespace(user_id=user.user_id, role_code="STUDENT", is_deactivated=False)
    user.is_deactivated = True
    db_session.commit()
    with pytest.raises(AppError) as caught:
        ProfileChangeService(db_session).prepare_resubmission(stale, row.change_request_id, submission_version=1)
    assert caught.value.code == "ACCOUNT_DEACTIVATED"


@pytest.mark.parametrize("case", ["no_confirmed_enrollment", "newer_registration"])
def test_preflight_requires_current_confirmed_enrollment(db_session, returned_context, case):
    _, user, enrolled, profile, row, _, _ = returned_context
    if case == "no_confirmed_enrollment":
        enrolled.confirmed_at = None
    else:
        db_session.add(CorScreening(student_user_id=user.user_id, purpose="REGISTRATION",
            status="AWAITING_CONFIRMATION", format_template_version="test",
            submitted_at=enrolled.submitted_at + timedelta(seconds=1)))
    db_session.commit()
    with pytest.raises(AppError) as caught:
        prepare(db_session, returned_context, submission_version=1)
    assert caught.value.code == "CORRECTION_RESUBMISSION_NOT_ALLOWED"
