"""Advisory owner revision flags use nonlocking current eligibility reads."""

from datetime import timedelta

import pytest
from sqlalchemy import event, func, select

from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_resubmission_preflight import returned_context  # noqa: F401
from .test_student_correction_reads import login


@pytest.mark.parametrize("legacy", [False, True])
def test_eligible_owner_gets_true_without_evidence_locks_or_mutation(db_session, db_client, returned_context, legacy):
    _, user, enrolled, profile, row, _, path = returned_context
    if legacy:
        row.submission_version = None
        row.status = "REJECTED"
        row.registered_values_json = row.extracted_values_json = None
        db_session.commit()
    login(db_client, user.email)
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)
    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        detail = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}")
        listing = db_client.get("/api/v1/profile-change-requests")
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert detail.status_code == listing.status_code == 200
    assert detail.json()["can_resubmit"] is True
    assert listing.json()["items"][0] == detail.json()
    assert detail.headers["cache-control"] == "no-store"
    assert not any("FOR UPDATE" in statement and "FROM users" not in statement
                   and "FROM user_sessions" not in statement for statement in statements)
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == count
    assert not db_session.new and not db_session.dirty
    assert not path.exists()  # Returned proof is gone; fresh upload is required.
    assert enrolled.status == "PASSED" and user.account_status == "ACTIVE" and profile.section == "A"


@pytest.mark.parametrize("case", ["pending", "approved", "expired_account", "expired_validity", "missing_profile",
    "number", "campus", "program", "malformed_lineage", "another_pending", "new_registration"])
def test_ineligible_or_obsolete_request_has_false_flag(db_session, db_client, returned_context, case):
    service, user, enrolled, profile, row, _, _ = returned_context
    if case in {"pending", "approved"}:
        row.status = case.upper()
    elif case == "expired_account":
        user.account_status = "VERIFICATION_EXPIRED"
    elif case == "expired_validity":
        enrolled.valid_until -= timedelta(days=400)
    elif case == "missing_profile":
        db_session.delete(profile)
    elif case == "number":
        profile.student_number = "20239999-B"
    elif case == "campus":
        service.accounts.find_campus(profile.campus_id).is_active = False
    elif case == "program":
        service.accounts.find_program(profile.program_id).is_active = False
    elif case == "malformed_lineage":
        row.root_change_request_id = row.change_request_id
    elif case == "another_pending":
        db_session.add(ProfileChangeRequest(student_user_id=user.user_id, cor_screening_id=enrolled.cor_screening_id,
            status="PENDING", requested_first_name="Juan", requested_last_name="Cruz", requested_year_level=1,
            requested_section="B"))
    else:
        db_session.add(CorScreening(student_user_id=user.user_id, purpose="REGISTRATION", status="AWAITING_CONFIRMATION",
            submitted_at=enrolled.submitted_at + timedelta(seconds=1), format_template_version="test"))
    db_session.commit()
    login(db_client, user.email)
    result = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}")
    assert result.status_code == 200 and result.json()["can_resubmit"] is False


def test_only_latest_terminal_version_is_eligible_and_correction_screenings_do_not_replace_enrollment(
    db_session, db_client, returned_context,
):
    _, user, enrolled, _, row, _, _ = returned_context
    child = ProfileChangeRequest(student_user_id=user.user_id, cor_screening_id=enrolled.cor_screening_id,
        status="RETURNED", submission_version=2, previous_change_request_id=row.change_request_id,
        root_change_request_id=row.change_request_id, requested_first_name="Juan", requested_last_name="Cruz",
        requested_year_level=1, requested_section="B")
    db_session.add_all([child, CorScreening(student_user_id=user.user_id, purpose="CORRECTION", status="FAILED",
        submitted_at=enrolled.submitted_at + timedelta(seconds=1), format_template_version="test")])
    db_session.commit()
    login(db_client, user.email)
    result = db_client.get("/api/v1/profile-change-requests")
    flags = {item["change_request"]["change_request_id"]: item["can_resubmit"] for item in result.json()["items"]}
    assert flags == {row.change_request_id: False, child.change_request_id: True}


def test_superadmin_has_no_owner_action_and_deactivated_student_is_denied(db_session, db_client, returned_context):
    _, user, _, _, row, _, _ = returned_context
    login(db_client, "edit-super@example.edu", "super-pass-1")
    result = db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}")
    assert result.status_code == 200 and result.json()["can_resubmit"] is False
    login(db_client, user.email)
    user.is_deactivated = True
    db_session.commit()
    assert db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}").status_code == 403


def test_stale_flag_does_not_authorize_post(db_session, db_client, returned_context):
    from .test_correction_resubmission_api import post
    _, user, enrolled, _, row, _, _ = returned_context
    login(db_client, user.email)
    assert db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}").json()["can_resubmit"] is True
    enrolled.valid_until -= timedelta(days=400)
    db_session.commit()
    result = post(db_client, row)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "CORRECTION_RESUBMISSION_NOT_ALLOWED"
    assert db_client.get(f"/api/v1/profile-change-requests/{row.change_request_id}").json()["can_resubmit"] is False


def test_screening_disabled_hides_revision_availability(db_client, returned_context, monkeypatch):
    from types import SimpleNamespace
    import app.config as module
    login(db_client, returned_context[1].email)
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(cor_screening_enabled=False))
    result = db_client.get(f"/api/v1/profile-change-requests/{returned_context[4].change_request_id}")
    assert result.status_code == 200 and result.json()["can_resubmit"] is False


def test_capability_read_does_not_weaken_preflight_locks(db_session, returned_context):
    _, user, _, _, row, _, _ = returned_context
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)
    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        ProfileChangeService(db_session).prepare_resubmission(user, row.change_request_id, submission_version=1)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    for table in ("users", "profile_change_requests", "cor_screenings"):
        assert any(f"FROM {table}" in statement and "FOR UPDATE" in statement for statement in statements)
