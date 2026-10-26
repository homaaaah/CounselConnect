"""Approval cannot overwrite changed registration context or obsolete lineage."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.modules.accounts.models import Campus, Program, User
from app.modules.accounts.repository import AccountsRepository
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening
from app.modules.profile_change.models import ProfileChangeRequest
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf


def approve(client, row):
    return client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/approve",
                       headers=csrf(client), json={"submission_version": row.submission_version})


def assert_denied(client, db, values, code):
    _, user, screening, profile, request, _, path = values
    original_names = user.first_name, user.middle_name, user.last_name
    original_profile = None if profile is None else (profile.student_number, profile.year_level, profile.section,
                                                    profile.campus_id, profile.program_id)
    count = db.scalar(select(func.count()).select_from(AuditEvent))
    response = approve(client, request)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] == {}
    db.refresh(request)
    db.refresh(user)
    assert (user.first_name, user.middle_name, user.last_name) == original_names
    assert request.status == "PENDING" and request.reviewed_at is request.reviewed_by_user_id is None
    if profile is not None:
        db.refresh(profile)
        assert (profile.student_number, profile.year_level, profile.section, profile.campus_id, profile.program_id) == original_profile
    assert path.exists() and user.account_status == "ACTIVE" and screening.status == "PASSED"
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == count
    return response


@pytest.mark.parametrize("field", ["first_name", "middle_name", "last_name", "year_level", "section",
    "student_number", "campus_id", "program_id", "academic_period", "valid_until"])
def test_changed_current_registered_or_enrollment_field_is_stale(db_session, db_client, evidence, field, caplog):
    _, user, screening, profile, _, _, _ = evidence
    if field in ("first_name", "middle_name", "last_name"):
        setattr(user, field, "PRIVATE-NEW-VALUE")
    elif field == "year_level":
        profile.year_level = 2
    elif field == "section":
        profile.section = "PRIVATE-NEW-VALUE"
    elif field == "student_number":
        profile.student_number = "20239999-B"
    elif field == "campus_id":
        campus = Campus(campus_name="Other Campus")
        db_session.add(campus)
        db_session.flush()
        profile.campus_id = campus.campus_id
    elif field == "program_id":
        original = db_session.get(Program, profile.program_id)
        program = Program(department_id=original.department_id, program_code="ALT", program_name="Other Program")
        db_session.add(program)
        db_session.flush()
        profile.program_id = program.program_id
    elif field == "academic_period":
        screening.extracted_academic_period = "PRIVATE-NEW-VALUE"
    else:
        screening.valid_until += timedelta(days=1)
    db_session.commit()
    response = assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_STALE")
    assert "PRIVATE-NEW-VALUE" not in response.text + caplog.text


@pytest.mark.parametrize("context", ["student_number", "campus_id", "program_id"])
def test_changed_protected_enrollment_source_is_stale(db_session, db_client, evidence, context):
    _, _, screening, _, _, _, _ = evidence
    # Change the enrollment source independently of the current profile.
    if context == "student_number":
        screening.extracted_student_number = "20239999-B"
    else:
        setattr(screening, f"extracted_{context}", None)
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_STALE")


@pytest.mark.parametrize("snapshot,value", [("registered_values_json", None), ("extracted_values_json", None),
    ("registered_values_json", {"section": "A"}), ("extracted_values_json", {"section": "A"}),
    ("registered_values_json", "PRIVATE-INVALID")])
def test_missing_or_partial_history_cannot_be_reconstructed(db_session, db_client, evidence, snapshot, value, caplog):
    row = evidence[4]
    setattr(row, snapshot, value)
    db_session.commit()
    response = assert_denied(db_client, db_session, evidence, "COR_EVIDENCE_UNAVAILABLE")
    assert "PRIVATE-INVALID" not in response.text + caplog.text


@pytest.mark.parametrize("field,value", [("first_name", None), ("year_level", "PRIVATE-INVALID"),
    ("valid_until", None), ("student_number", None), ("campus_id", None), ("program_id", None)])
def test_invalid_recorded_baseline_is_unavailable(db_session, db_client, evidence, field, value):
    row = evidence[4]
    row.registered_values_json = {**row.registered_values_json, field: value}
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "COR_EVIDENCE_UNAVAILABLE")


def test_missing_registered_screening_identity_is_unknown(db_session, db_client, evidence):
    evidence[4].registered_cor_screening_id = None
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "COR_EVIDENCE_UNAVAILABLE")


@pytest.mark.parametrize("field", ["student_number", "first_name", "last_name", "year_level", "section"])
def test_required_extraction_context_cannot_be_supplied_from_baseline(db_session, db_client, evidence, field):
    row = evidence[4]
    row.extracted_values_json = {**row.extracted_values_json, field: None}
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "COR_EVIDENCE_UNAVAILABLE")


def test_explicit_unmapped_extraction_references_remain_valid_known_context(db_session, db_client, evidence):
    row = evidence[4]
    row.extracted_values_json = {**row.extracted_values_json, "campus_id": None, "program_id": None}
    db_session.commit()
    assert approve(db_client, row).status_code == 200


def test_wrong_registered_screening_identity_is_stale(db_session, db_client, evidence):
    _, user, _, _, row, _, _ = evidence
    other = CorScreening(student_user_id=user.user_id, status="PASSED", purpose="CORRECTION",
                         format_template_version="test", submitted_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.flush()
    row.registered_cor_screening_id = other.cor_screening_id
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_STALE")


def test_missing_current_profile_is_stale(db_session, db_client, evidence):
    db_session.delete(evidence[3])
    db_session.commit()
    values = (*evidence[:3], None, *evidence[4:])
    assert_denied(db_client, db_session, values, "CHANGE_REQUEST_STALE")


@pytest.mark.parametrize("kind", ["campus", "program"])
def test_inactive_reference_is_stale(db_session, db_client, evidence, kind):
    profile = evidence[3]
    reference = db_session.get(Campus if kind == "campus" else Program,
                               profile.campus_id if kind == "campus" else profile.program_id)
    reference.is_active = False
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_STALE")


@pytest.mark.parametrize("later_upload", [False, True])
def test_changed_confirmed_enrollment_identity_is_stale(db_session, db_client, evidence, later_upload):
    _, user, screening, _, _, _, _ = evidence
    # Confirmation identity must stay bound for older and newer uploads alike.
    db_session.add(CorScreening(student_user_id=user.user_id, status="PASSED", purpose="REGISTRATION",
        format_template_version="test", submitted_at=screening.submitted_at + (timedelta(seconds=1) if later_upload else -timedelta(days=1)),
        confirmed_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        extracted_student_number="20231234-A", extracted_academic_period="2026-2027",
        valid_until=screening.valid_until))
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_STALE")


def test_unrelated_account_timestamp_does_not_make_baseline_stale(db_session, db_client, evidence):
    _, user, _, profile, row, _, path = evidence
    user.updated_at = datetime.now(timezone.utc) + timedelta(days=1)
    db_session.commit()
    response = approve(db_client, row)
    assert response.status_code == 200
    assert row.status == "APPROVED" and profile.section == "B" and not path.exists()


def copy_request(db, row, **overrides):
    fields = ("student_user_id", "cor_screening_id", "registered_cor_screening_id", "registered_values_json",
        "extracted_values_json", "evidence_file_id", "evidence_sha256_hash", "evidence_uploaded_at", "evidence_expires_at",
        "requested_first_name", "requested_middle_name", "requested_last_name", "requested_year_level", "requested_section")
    values = {field: getattr(row, field) for field in fields}
    child = ProfileChangeRequest(**{**values, "status": "RETURNED", "submission_version": 2, **overrides})
    db.add(child)
    db.flush()
    return child


def test_obsolete_pending_version_with_successor_cannot_approve(db_session, db_client, evidence):
    row = evidence[4]
    copy_request(db_session, row, previous_change_request_id=row.change_request_id, root_change_request_id=row.change_request_id)
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_VERSION_CONFLICT")


@pytest.mark.parametrize("kind", ["root_version", "self_root", "foreign_root", "missing_predecessor", "approved_parent", "version_gap"])
def test_invalid_lineage_cannot_approve(db_session, db_client, evidence, kind):
    row = evidence[4]
    if kind == "root_version":
        row.submission_version = 2
    elif kind == "self_root":
        row.root_change_request_id = row.change_request_id
    else:
        # A separate terminal root, with no synthetic historical version fixup.
        root = copy_request(db_session, row, submission_version=1,
                            status="APPROVED" if kind == "approved_parent" else "RETURNED")
        if kind == "foreign_root":
            root.student_user_id = db_session.scalar(select(User.user_id).where(User.role_code == "SUPERADMIN"))
        row.root_change_request_id = root.change_request_id
        row.previous_change_request_id = None if kind == "missing_predecessor" else root.change_request_id
        row.submission_version = 3 if kind == "version_gap" else 2
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_VERSION_CONFLICT")


@pytest.mark.parametrize("legacy", [False, True])
def test_valid_latest_chain_preserves_legacy_unknown_version(db_session, db_client, evidence, legacy):
    _, _, _, profile, row, _, path = evidence
    root = copy_request(db_session, row, submission_version=None if legacy else 1, status="REJECTED" if legacy else "RETURNED")
    row.root_change_request_id = root.change_request_id
    row.previous_change_request_id = root.change_request_id
    row.submission_version = 1 if legacy else 2
    db_session.commit()
    response = approve(db_client, row)
    assert response.status_code == 200
    assert profile.section == "B" and not path.exists()
    assert root.submission_version == (None if legacy else 1)


def test_orphaned_link_cannot_be_treated_as_a_valid_linear_history(db_session, db_client, evidence):
    row = evidence[4]
    root = copy_request(db_session, row, submission_version=1)
    row.root_change_request_id = root.change_request_id
    row.previous_change_request_id = root.change_request_id
    row.submission_version = 2
    db_session.flush()
    copy_request(db_session, row, root_change_request_id=root.change_request_id, submission_version=1)
    db_session.commit()
    assert_denied(db_client, db_session, evidence, "CHANGE_REQUEST_VERSION_CONFLICT")


def test_current_profile_is_read_under_lock_before_application(db_session, db_client, evidence, monkeypatch):
    original = AccountsRepository.lock_student_profile

    def changed(self, student_id):
        profile = original(self, student_id)
        profile.section = "PRIVATE-NEWER"
        return profile

    monkeypatch.setattr(AccountsRepository, "lock_student_profile", changed)
    response = approve(db_client, evidence[4])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CHANGE_REQUEST_STALE"
    assert evidence[3].section == "PRIVATE-NEWER" and evidence[4].status == "PENDING"
    assert evidence[-1].exists()
