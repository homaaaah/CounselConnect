"""Changed-field-only approval and final deadline/rollback before commit."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select

from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.service import as_utc
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf


def approve(client, row):
    return client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/approve",
                       headers=csrf(client), json={"submission_version": 1})


def decisions(db, row):
    return list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_approved",
        AuditEvent.target_id == row.change_request_id)))


def unchanged(db, values):
    _, user, _, profile, row, _, path = values
    db.refresh(user)
    db.refresh(profile)
    db.refresh(row)
    assert (user.first_name, user.middle_name, user.last_name) == ("Juan", "Dela", "Cruz")
    assert (profile.year_level, profile.section) == (1, "A")
    assert row.status == "PENDING" and row.reviewed_at is row.reviewed_by_user_id is None
    assert decisions(db, row) == []
    assert path.exists() and user.account_status == "ACTIVE"


def test_case_equivalent_unmodified_names_are_not_written_or_retimestamped(db_session, db_client, evidence):
    _, user, _, profile, row, _, path = evidence
    row.requested_first_name = "  JUAN  "
    row.requested_middle_name = " dela "
    row.requested_last_name = "CRUZ"
    db_session.commit()
    original_updated_at = user.updated_at
    original_snapshot = dict(row.registered_values_json)
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.startswith("UPDATE users"):
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        response = approve(db_client, row)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert response.status_code == 200
    db_session.refresh(user)
    assert (user.first_name, user.middle_name, user.last_name) == ("Juan", "Dela", "Cruz")
    assert as_utc(user.updated_at) == as_utc(original_updated_at) and statements == []
    assert profile.section == "B" and not path.exists()
    assert row.requested_first_name == "  JUAN  " and row.registered_values_json == original_snapshot
    audit = decisions(db_session, row)
    assert len(audit) == 1
    assert audit[0].metadata_json == {"previous_status": "PENDING", "status": "APPROVED", "submission_version": 1}


@pytest.mark.parametrize("field,value", [("first_name", "Maria"), ("middle_name", None),
    ("last_name", "Reyes"), ("year_level", 2), ("section", " B ")])
def test_only_the_changed_supported_field_is_applied(db_session, db_client, evidence, field, value):
    _, user, _, profile, row, _, _ = evidence
    for key in ("first_name", "middle_name", "last_name", "year_level", "section"):
        setattr(row, f"requested_{key}", row.registered_values_json[key])
    setattr(row, f"requested_{field}", value)
    db_session.commit()
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.startswith("UPDATE users") or statement.startswith("UPDATE student_profiles"):
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        response = approve(db_client, row)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert response.status_code == 200
    target = profile if field in ("year_level", "section") else user
    assert getattr(target, field) == (value.strip() if isinstance(value, str) else value)
    assert len(statements) == 1
    assert f"{field}=" in statements[0]
    for protected in ("student_number=", "campus_id=", "program_id=", "account_status=", "email=", "is_deactivated="):
        assert protected not in statements[0]


def test_unicode_equivalent_proposal_leaves_registered_spelling_intact(db_session, db_client, evidence):
    _, user, screening, profile, row, _, _ = evidence
    # Seed a coherent original Unicode spelling and its equivalent proposal.
    user.first_name = screening.extracted_first_name = "Straße"
    row.extracted_values_json = {**row.extracted_values_json, "first_name": "Straße"}
    row.registered_values_json = {**row.registered_values_json, "first_name": "Straße"}
    row.requested_first_name = "STRASSE"
    db_session.commit()
    assert approve(db_client, row).status_code == 200
    assert user.first_name == "Straße" and profile.section == "B"


def expire_clock(monkeypatch, deadline):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return as_utc(deadline)

    monkeypatch.setattr("app.modules.profile_change.service.datetime", Clock)


def test_deadline_after_baseline_validation_denies_before_writes(db_session, db_client, evidence, monkeypatch):
    row = evidence[4]
    original = ProfileChangeService._require_registered_baseline

    def checked(self, request):
        result = original(self, request)
        expire_clock(monkeypatch, request.evidence_expires_at)
        return result

    monkeypatch.setattr(ProfileChangeService, "_require_registered_baseline", checked)
    response = approve(db_client, row)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["availability"] == "EXPIRED"
    unchanged(db_session, evidence)


def test_final_deadline_after_sql_flush_rolls_back_profile_decision_and_audit(db_session, db_client, evidence, monkeypatch):
    row = evidence[4]
    original = AuditService.record
    flushed = []

    def record_then_expire(self, actor_id, event_type, target_type, target_id, **kwargs):
        original(self, actor_id, event_type, target_type, target_id, **kwargs)
        if event_type == "profile_change_approved":
            expire_clock(monkeypatch, row.evidence_expires_at)

    def after_flush(session, _context):
        if any(isinstance(item, AuditEvent) and item.event_type == "profile_change_approved" for item in session.new):
            flushed.append(True)

    monkeypatch.setattr(AuditService, "record", record_then_expire)
    event.listen(db_session, "after_flush", after_flush)
    try:
        response = approve(db_client, row)
    finally:
        event.remove(db_session, "after_flush", after_flush)
    assert response.status_code == 409 and flushed == [True]
    assert response.json()["error"]["code"] == "COR_EVIDENCE_UNAVAILABLE"
    assert response.json()["error"]["details"]["availability"] == "EXPIRED"
    unchanged(db_session, evidence)  # no caller rollback needed


@pytest.mark.parametrize("failure", ["audit", "flush", "commit"])
def test_application_failures_rollback_without_caller_intervention(db_session, evidence, monkeypatch, failure):
    row = evidence[4]
    actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
    if failure == "audit":
        original = AuditService.record

        def fail(self, actor_id, event_type, target_type, target_id, **kwargs):
            original(self, actor_id, event_type, target_type, target_id, **kwargs)
            if event_type == "profile_change_approved":
                self.repository.session.flush()
                raise RuntimeError("Injected audit failure")

        monkeypatch.setattr(AuditService, "record", fail)
    elif failure == "flush":
        original = db_session.flush
        injected = []

        def fail(*args, **kwargs):
            result = original(*args, **kwargs)
            if not injected and row.status == "APPROVED":
                injected.append(True)
                raise RuntimeError("Injected flush failure")
            return result

        monkeypatch.setattr(db_session, "flush", fail)
    else:
        def fail():
            raise RuntimeError("Injected commit failure")

        monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        ProfileChangeService(db_session).approve(actor, row.change_request_id, submission_version=1)
    unchanged(db_session, evidence)


def test_cleanup_is_only_invoked_after_atomic_commit(db_session, db_client, evidence, monkeypatch):
    service, _, _, profile, row, _, path = evidence
    committed = []
    original_commit = db_session.commit
    original_cleanup = service.__class__.cleanup_screening_files

    def commit():
        original_commit()
        committed.append(True)

    def cleanup(self, screening_id):
        assert committed and row.status == "APPROVED" and profile.section == "B"
        assert len(decisions(db_session, row)) == 1 and path.exists()
        return original_cleanup(self, screening_id)

    monkeypatch.setattr(db_session, "commit", commit)
    monkeypatch.setattr(service.__class__, "cleanup_screening_files", cleanup)
    assert approve(db_client, row).status_code == 200
    assert not path.exists()
