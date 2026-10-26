"""Locked resubmission versus scoped synthetic eligibility/enrollment writes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.accounts.models import StudentProfile, User
from app.modules.accounts.repository import AccountsRepository
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.models import CorScreening
from app.modules.cor_screening.repository import CorScreeningRepository
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_decision_concurrency import committed_correction  # noqa: F401
from .test_correction_resubmission_concurrency import predecessor  # noqa: F401


@pytest.mark.parametrize("change", ["deactivation", "expired_validity", "new_registration"])
@pytest.mark.parametrize("revision_first", [False, True])
def test_resubmission_serializes_with_current_eligibility_change(
    mysql_test_engine, predecessor, monkeypatch, change, revision_first,
):
    data = predecessor
    with Session(mysql_test_engine) as db:
        root = db.get(ProfileChangeRequest, data["request"])
        enrollment_id = root.registered_cor_screening_id
        old_snapshot = root.registered_values_json.copy()
    held, competing, release = Event(), Event(), Event()
    ids = []
    record = AuditService.record
    processed = []
    screen = CorScreeningService.screen_correction_document
    def count_screen(self, *args, **kwargs):
        processed.append(True)
        return screen(self, *args, **kwargs)
    monkeypatch.setattr(CorScreeningService, "screen_correction_document", count_screen)

    def pause(self, actor, event_type, *args, **kwargs):
        result = record(self, actor, event_type, *args, **kwargs)
        if revision_first and event_type == "profile_change_resubmitted":
            self.repository.session.flush()
            held.set()
            assert release.wait(10)
        return result
    monkeypatch.setattr(AuditService, "record", pause)

    def observe_waiter(connection, _cursor, statement, parameters, _context, _many):
        if (connection.info.get("eligibility_waiter") and "FROM users" in statement
                and "FOR UPDATE" in statement and data["student"] in parameters.values()):
            competing.set()

    def open_session(db, waiter):
        db.execute(text("SET SESSION innodb_lock_wait_timeout=5"))
        db.connection().info["eligibility_waiter"] = waiter
        ids.append(db.scalar(text("SELECT CONNECTION_ID()")))

    def revise():
        with Session(mysql_test_engine, autoflush=False, expire_on_commit=False) as db:
            open_session(db, not revision_first)
            # Hold actual stale ORM objects and an earlier repeatable-read snapshot.
            student = db.get(User, data["student"])
            cached_profile = db.get(StudentProfile, data["student"])
            cached_enrollment = db.get(CorScreening, enrollment_id)
            assert student.is_deactivated is False
            assert cached_profile.section == "A" and cached_enrollment.valid_until is not None
            try:
                row = ProfileChangeService(db).resubmit(student, data["request"], submission_version=1,
                    proposed_changes='{"section":"B"}', content=b"%PDF-1.4 eligibility race", filename="cor.pdf")
                return "CREATED", row.change_request_id
            except AppError as exc:
                return exc.code, None
            finally:
                db.connection().info["eligibility_waiter"] = False

    def mutate():
        with Session(mysql_test_engine, autoflush=False, expire_on_commit=False) as db:
            open_session(db, revision_first)
            try:
                student = AccountsRepository(db).lock_user(data["student"])
                enrolled = CorScreeningRepository(db).lock_screening(enrollment_id)
                if change == "deactivation":
                    student.is_deactivated = True
                elif change == "expired_validity":
                    enrolled.valid_until -= timedelta(days=400)
                else:
                    db.add(CorScreening(student_user_id=student.user_id, purpose="REGISTRATION",
                        status="AWAITING_CONFIRMATION", format_template_version="test",
                        submitted_at=enrolled.submitted_at + timedelta(seconds=1)))
                db.flush()
                if not revision_first:
                    held.set()
                    assert release.wait(10)
                db.commit()
                return "CHANGED"
            finally:
                db.connection().info["eligibility_waiter"] = False

    event.listen(mysql_test_engine, "before_cursor_execute", observe_waiter)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(revise if revision_first else mutate)
            try:
                assert held.wait(10)
                second = executor.submit(mutate if revision_first else revise)
                assert competing.wait(10)
            finally:
                release.set()
            results = first.result(timeout=15), second.result(timeout=15)
    finally:
        release.set()
        event.remove(mysql_test_engine, "before_cursor_execute", observe_waiter)
    assert len(set(ids)) == 2
    revision_result = results[0] if revision_first else results[1]
    assert len(processed) == int(revision_first)
    assert revision_result[0] == ("CREATED" if revision_first else
        "ACCOUNT_DEACTIVATED" if change == "deactivation" else "CORRECTION_RESUBMISSION_NOT_ALLOWED")
    with Session(mysql_test_engine) as db:
        student = db.get(User, data["student"])
        enrolled = db.get(CorScreening, enrollment_id)
        assert student.account_status == "ACTIVE"
        assert student.is_deactivated is (change == "deactivation")
        assert enrolled.status == "PASSED" and enrolled.confirmed_at is not None
        assert db.get(StudentProfile, data["student"]).section == "A"
        root = db.get(ProfileChangeRequest, data["request"])
        assert root.status == "RETURNED" and root.registered_values_json == old_snapshot
        children = list(db.scalars(select(ProfileChangeRequest).where(
            ProfileChangeRequest.previous_change_request_id == data["request"])))
        assert len(children) == int(revision_first)
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_resubmitted",
            AuditEvent.actor_user_id == data["student"])))
        assert len(audits) == int(revision_first)
        if revision_first:
            assert children[0].registered_cor_screening_id == enrollment_id
            assert children[0].registered_values_json == old_snapshot
            availability = CorScreeningService(db).correction_evidence_status(children[0])["availability"]
            assert availability == ("REPLACED" if change == "new_registration" else "UNAVAILABLE")
