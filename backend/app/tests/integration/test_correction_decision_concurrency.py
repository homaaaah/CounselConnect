"""Real independent MySQL connections competing over one committed correction."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.accounts.models import Campus, Department, Program, StudentProfile, User
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.models import CorScreening
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_profile_change import _payload, good_result, stub_screening


@pytest.fixture(params=["REGISTRATION", "CORRECTION"])
def committed_correction(mysql_test_engine, monkeypatch, request):
    """Commit only synthetic owned rows in the fixture's disposable schema."""
    tag = uuid4().hex[:12]
    with Session(mysql_test_engine, autoflush=False, expire_on_commit=False) as db:
        before = set(db.scalars(select(AuditEvent.audit_event_id)))
        campus = Campus(campus_name=f"Race Campus {tag}")
        department = Department(department_name=f"Race Department {tag}")
        db.add_all([campus, department])
        db.flush()
        program = Program(department_id=department.department_id, program_code=f"R{tag}", program_name=f"Race Program {tag}")
        db.add(program)
        db.flush()
        reviewers = [User(email=f"race-{tag}-{index}@example.edu", password_hash="not-a-login-credential",
            role_code="SUPERADMIN", account_status="ACTIVE", first_name="Reviewer", last_name=str(index)) for index in (1, 2)]
        db.add_all(reviewers)
        db.commit()
        stub_screening(monkeypatch, good_result(campus=campus.campus_name, course=program.program_name))
        service = CorScreeningService(db)
        student, screening, _, _, _ = service.register_with_cor(f"race-{tag}@example.edu", "password1", b"%PDF-1.4 race", "cor.pdf")
        file = service.repository.find_active_file(screening.cor_screening_id)
        path = Path(service._storage_path(file.storage_key))
        _, _, _, correction = service.request_edit(student, _payload(campus.campus_id, program.program_id, section="B"))
        if request.param == "CORRECTION":
            proof = CorScreening(student_user_id=student.user_id, purpose="CORRECTION", status="PASSED",
                format_template_version="test", submitted_at=screening.submitted_at,
                extracted_student_number=screening.extracted_student_number,
                extracted_campus_id=screening.extracted_campus_id, extracted_program_id=screening.extracted_program_id,
                extracted_academic_period=screening.extracted_academic_period)
            db.add(proof)
            db.flush()
            correction.cor_screening_id = proof.cor_screening_id
            file.cor_screening_id = proof.cor_screening_id
        db.commit()
        values = {"student": student.user_id, "request": correction.change_request_id,
                  "reviewers": [reviewer.user_id for reviewer in reviewers], "path": path}
        audit_ids = set(db.scalars(select(AuditEvent.audit_event_id))) - before
        reference_ids = campus.campus_id, program.program_id, department.department_id
    try:
        yield values
    finally:
        # Explicitly remove only this fixture's committed rows before other
        # tests use the shared disposable schema. No application DB is used.
        with Session(mysql_test_engine) as db:
            db.execute(delete(AuditEvent).where(AuditEvent.audit_event_id.in_(audit_ids)))
            db.execute(delete(AuditEvent).where(AuditEvent.target_type == "profile_change_request",
                                              AuditEvent.target_id == values["request"]))
            db.execute(delete(ProfileChangeRequest).where(ProfileChangeRequest.student_user_id == values["student"]))
            db.execute(delete(CorScreening).where(CorScreening.student_user_id == values["student"]))
            db.execute(delete(User).where(User.user_id.in_([values["student"], *values["reviewers"]])))
            db.execute(delete(Program).where(Program.program_id == reference_ids[1]))
            db.execute(delete(Campus).where(Campus.campus_id == reference_ids[0]))
            db.execute(delete(Department).where(Department.department_id == reference_ids[2]))
            db.commit()
        path.unlink(missing_ok=True)


def race_decisions(mysql_test_engine, data, actions, same_reviewer, *, fail_first=None, monkeypatch=None):
    locked, competing, release = Event(), Event(), Event()
    connection_ids = []
    observer_ids = []
    second_reviewer = data["reviewers"][0 if same_reviewer else 1]
    # This is the exact first lock the competitor must wait on.
    blocked_user = data["reviewers"][0] if same_reviewer else data["student"]

    def observe_uncommitted():
        # A third connection must not observe a partially applied decision,
        # even after SQL flush and before the injected failure/rollback.
        with Session(mysql_test_engine) as observer:
            observer_ids.append(observer.scalar(text("SELECT CONNECTION_ID()")))
            assert observer.get(ProfileChangeRequest, data["request"]).status == "PENDING"
            assert observer.get(StudentProfile, data["student"]).section == "A"
            assert observer.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.event_type == "profile_change_approved", AuditEvent.target_id == data["request"])) == 0
            assert data["path"].exists()

    if fail_first == "audit":
        original_record = AuditService.record

        def fail_record(self, actor_id, event_type, target_type, target_id, **kwargs):
            original_record(self, actor_id, event_type, target_type, target_id, **kwargs)
            if self.repository.session.info.get("fail_race") and event_type == "profile_change_approved":
                self.repository.session.flush()
                observe_uncommitted()
                raise RuntimeError("Injected concurrent rollback")

        monkeypatch.setattr(AuditService, "record", fail_record)

    def before_execute(connection, _cursor, statement, parameters, _context, _many):
        if (connection.info.get("correction_competitor") and "FOR UPDATE" in statement and "FROM users" in statement
                and blocked_user in parameters.values()):
            competing.set()

    def decide(first):
        with Session(mysql_test_engine, autoflush=False, expire_on_commit=False) as db:
            db.execute(text("SET SESSION innodb_lock_wait_timeout=5"))
            db.connection().info["correction_competitor"] = not first
            db.info["fail_race"] = first and fail_first is not None
            connection_ids.append(db.scalar(text("SELECT CONNECTION_ID()")))
            actor = db.get(User, data["reviewers"][0] if first else second_reviewer)
            cached = db.get(ProfileChangeRequest, data["request"])
            assert cached.status == "PENDING"  # both begin with a stale-capable cache
            service = ProfileChangeService(db)
            if first and fail_first == "commit":
                def fail_commit():
                    observe_uncommitted()
                    raise RuntimeError("Injected concurrent rollback")

                db.commit = fail_commit
            if first:
                original = service._lock_request_after_student

                def hold(request_id):
                    row = original(request_id)
                    locked.set()
                    assert release.wait(10)
                    return row

                service._lock_request_after_student = hold
            action = actions[0 if first else 1]
            try:
                if action == "approve":
                    service.approve(actor, data["request"], submission_version=1)
                elif action == "return":
                    service.return_request(actor, data["request"], "Check the submitted section.", submission_version=1)
                else:
                    service.reject(actor, data["request"], "Check the submitted section.", submission_version=1)
                return action
            except AppError as error:
                db.rollback()
                return error.code
            except DBAPIError as error:
                db.rollback()
                return f"DB_ERROR_{error.orig.args[0]}"  # safe diagnostic; no SQL/values
            except RuntimeError as error:
                db.rollback()
                assert str(error) == "Injected concurrent rollback"
                return "INJECTED_FAILURE"

    event.listen(mysql_test_engine, "before_cursor_execute", before_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(decide, True)
            try:
                assert locked.wait(10)
                second = executor.submit(decide, False)
                assert competing.wait(10)
            finally:
                release.set()
            assert first.result(timeout=15) == ("INJECTED_FAILURE" if fail_first else actions[0])
            assert second.result(timeout=15) == (actions[1] if fail_first else "CHANGE_REQUEST_NOT_PENDING")
    finally:
        event.remove(mysql_test_engine, "before_cursor_execute", before_execute)
    assert len(set(connection_ids)) == 2
    if fail_first:
        assert len(observer_ids) == 1 and observer_ids[0] not in connection_ids
    with Session(mysql_test_engine) as db:
        row = db.get(ProfileChangeRequest, data["request"])
        profile = db.get(StudentProfile, data["student"])
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.target_type == "profile_change_request",
            AuditEvent.target_id == data["request"], AuditEvent.event_type.in_(["profile_change_approved", "profile_change_rejected", "profile_change_returned"]))))
        winner_action = actions[1] if fail_first else actions[0]
        assert row.status == {"approve": "APPROVED", "reject": "RETURNED", "return": "RETURNED"}[winner_action]
        assert profile.section == ("B" if winner_action == "approve" else "A")
        assert row.reviewed_by_user_id == (second_reviewer if fail_first else data["reviewers"][0])
        assert len(audits) == 1
        assert not data["path"].exists()


@pytest.mark.parametrize("actions", [("approve", "approve"), ("approve", "reject"), ("reject", "approve")])
@pytest.mark.parametrize("same_reviewer", [False, True])
def test_competing_decisions_have_one_winner(mysql_test_engine, committed_correction, actions, same_reviewer):
    race_decisions(mysql_test_engine, committed_correction, actions, same_reviewer)


@pytest.mark.parametrize("actions", [("return", "approve"), ("approve", "return"), ("return", "return")])
@pytest.mark.parametrize("same_reviewer", [False, True])
def test_competing_returns_have_one_winner(mysql_test_engine, committed_correction, actions, same_reviewer):
    race_decisions(mysql_test_engine, committed_correction, actions, same_reviewer)


@pytest.mark.parametrize("failure", ["audit", "commit"])
@pytest.mark.parametrize("same_reviewer", [False, True])
def test_waiting_approval_wins_after_first_real_transaction_rolls_back(
    mysql_test_engine, committed_correction, monkeypatch, failure, same_reviewer,
):
    race_decisions(mysql_test_engine, committed_correction, ("approve", "approve"), same_reviewer,
                   fail_first=failure, monkeypatch=monkeypatch)


@pytest.mark.parametrize("field", ["section", "first_name"])
def test_committed_newer_profile_survives_waiting_stale_approval(mysql_test_engine, committed_correction, field):
    data = committed_correction
    writer_locked, competing, release = Event(), Event(), Event()
    connection_ids = []

    def before_execute(connection, _cursor, statement, parameters, _context, _many):
        if (connection.info.get("stale_approval") and "FOR UPDATE" in statement and "FROM users" in statement
                and data["student"] in parameters.values()):
            competing.set()

    def writer():
        with Session(mysql_test_engine) as db:
            connection_ids.append(db.scalar(text("SELECT CONNECTION_ID()")))
            user = db.scalar(select(User).where(User.user_id == data["student"]).with_for_update())
            profile = db.get(StudentProfile, data["student"])
            setattr(profile if field == "section" else user, field, "NEWER-REGISTERED")
            db.flush()
            writer_locked.set()
            assert release.wait(10)
            db.commit()

    def reviewer():
        with Session(mysql_test_engine, autoflush=False, expire_on_commit=False) as db:
            db.execute(text("SET SESSION innodb_lock_wait_timeout=5"))
            db.connection().info["stale_approval"] = True
            connection_ids.append(db.scalar(text("SELECT CONNECTION_ID()")))
            actor = db.get(User, data["reviewers"][0])
            old_user = db.get(User, data["student"])
            old_profile = db.get(StudentProfile, data["student"])
            assert getattr(old_profile if field == "section" else old_user, field) != "NEWER-REGISTERED"
            try:
                ProfileChangeService(db).approve(actor, data["request"], submission_version=1)
                return "approved"
            except AppError as error:
                db.rollback()
                return error.code

    event.listen(mysql_test_engine, "before_cursor_execute", before_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(writer)
            try:
                assert writer_locked.wait(10)
                second = executor.submit(reviewer)
                assert competing.wait(10)
            finally:
                release.set()
            first.result(timeout=15)
            assert second.result(timeout=15) == "CHANGE_REQUEST_STALE"
    finally:
        event.remove(mysql_test_engine, "before_cursor_execute", before_execute)
    assert len(set(connection_ids)) == 2
    with Session(mysql_test_engine) as db:
        user = db.get(User, data["student"])
        profile = db.get(StudentProfile, data["student"])
        assert getattr(profile if field == "section" else user, field) == "NEWER-REGISTERED"
        assert db.get(ProfileChangeRequest, data["request"]).status == "PENDING"
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == "profile_change_approved", AuditEvent.target_id == data["request"])) == 0
        assert data["path"].exists()
