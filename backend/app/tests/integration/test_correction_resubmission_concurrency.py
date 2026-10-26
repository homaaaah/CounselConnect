"""Independent MySQL connections revising the same committed predecessor."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.accounts.models import StudentProfile, User
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_decision_concurrency import committed_correction  # noqa: F401


@pytest.fixture
def predecessor(mysql_test_engine, committed_correction):
    data = committed_correction
    with Session(mysql_test_engine, expire_on_commit=False) as db:
        ProfileChangeService(db).return_request(db.get(User, data["reviewers"][0]), data["request"],
            "Recheck section.", submission_version=1)
    try:
        yield data
    finally:
        # Descendants have RESTRICT lineage FKs; release only this fixture's
        # descendants and their audit/files before the parent fixture teardown.
        with Session(mysql_test_engine) as db:
            ids = list(db.scalars(select(ProfileChangeRequest.change_request_id).where(
                ProfileChangeRequest.student_user_id == data["student"],
                ProfileChangeRequest.change_request_id != data["request"],
            ).order_by(ProfileChangeRequest.change_request_id.desc())))
            proof_ids = list(db.scalars(select(CorScreening.cor_screening_id).where(
                CorScreening.student_user_id == data["student"])))
            keys = list(db.scalars(select(CorScreeningFile.storage_key).where(
                CorScreeningFile.cor_screening_id.in_(proof_ids))))
            for request_id in ids:
                db.execute(delete(AuditEvent).where(AuditEvent.target_type == "profile_change_request",
                    AuditEvent.target_id == request_id))
                db.execute(delete(ProfileChangeRequest).where(ProfileChangeRequest.change_request_id == request_id))
            db.commit()
            for key in keys:
                assert CorScreeningService(db)._delete_cor_bytes(key)


@pytest.mark.parametrize("scenario", ["versioned", "legacy", "first_rollback"])
def test_same_predecessor_has_one_committed_successor(mysql_test_engine, predecessor, monkeypatch, scenario):
    data = predecessor
    expected_version = None if scenario == "legacy" else 1
    with Session(mysql_test_engine) as db:
        root = db.get(ProfileChangeRequest, data["request"])
        if scenario == "legacy":
            root.submission_version = None
            root.status = "REJECTED"
            db.commit()
        original = root.status, root.requested_section, root.registered_values_json.copy()
    held, competing, release = Event(), Event(), Event()
    connection_ids = []
    record = AuditService.record

    def pause_after_flush(self, actor, event_type, *args, **kwargs):
        result = record(self, actor, event_type, *args, **kwargs)
        db = self.repository.session
        if event_type == "profile_change_resubmitted" and db.info.get("first_revision"):
            db.flush()
            held.set()
            assert release.wait(10)
            if scenario == "first_rollback":
                raise RuntimeError("Injected first revision rollback")
        return result

    monkeypatch.setattr(AuditService, "record", pause_after_flush)

    def observe_lock(connection, _cursor, statement, parameters, _context, _many):
        if (connection.info.get("revision_competitor") and "FROM users" in statement
                and "FOR UPDATE" in statement and data["student"] in parameters.values()):
            competing.set()

    def revise(first):
        with Session(mysql_test_engine, autoflush=False, expire_on_commit=False) as db:
            db.execute(text("SET SESSION innodb_lock_wait_timeout=5"))
            db.connection().info["revision_competitor"] = not first
            db.info["first_revision"] = first
            connection_ids.append(db.scalar(text("SELECT CONNECTION_ID()")))
            # Seed a repeatable-read snapshot before the winner's commit.
            db.get(ProfileChangeRequest, data["request"])
            student = db.get(User, data["student"])
            try:
                row = ProfileChangeService(db).resubmit(student, data["request"],
                    submission_version=expected_version, proposed_changes='{"section":"B"}',
                    content=b"%PDF-1.4 concurrent revision", filename="cor.pdf")
                return "CREATED", row.change_request_id
            except AppError as exc:
                return exc.code, None
            except RuntimeError as exc:
                assert str(exc) == "Injected first revision rollback"
                return "ROLLED_BACK", None
            finally:
                db.connection().info["revision_competitor"] = False

    event.listen(mysql_test_engine, "before_cursor_execute", observe_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(revise, True)
            try:
                assert held.wait(10)
                second = executor.submit(revise, False)
                assert competing.wait(10)
                with Session(mysql_test_engine) as observer:
                    connection_ids.append(observer.scalar(text("SELECT CONNECTION_ID()")))
                    assert list(observer.scalars(select(ProfileChangeRequest).where(
                        ProfileChangeRequest.previous_change_request_id == data["request"]))) == []
                    assert observer.get(StudentProfile, data["student"]).section == "A"
            finally:
                release.set()
            outcomes = [first.result(timeout=15), second.result(timeout=15)]
    finally:
        release.set()
        event.remove(mysql_test_engine, "before_cursor_execute", observe_lock)
    assert len(set(connection_ids)) == 3
    assert outcomes[0][0] == ("ROLLED_BACK" if scenario == "first_rollback" else "CREATED")
    assert outcomes[1][0] == ("CREATED" if scenario == "first_rollback" else "CHANGE_REQUEST_VERSION_CONFLICT")
    with Session(mysql_test_engine) as db:
        children = list(db.scalars(select(ProfileChangeRequest).where(
            ProfileChangeRequest.previous_change_request_id == data["request"])))
        assert len(children) == 1
        row = children[0]
        assert row.status == "PENDING" and row.submission_version == (1 if scenario == "legacy" else 2)
        root = db.get(ProfileChangeRequest, data["request"])
        assert original == (root.status, root.requested_section, root.registered_values_json)
        assert db.get(StudentProfile, data["student"]).section == "A"
        assert db.get(User, data["student"]).account_status == "ACTIVE"
        audit = list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_resubmitted",
            AuditEvent.target_id == row.change_request_id)))
        assert len(audit) == 1
        assert CorScreeningService(db).correction_evidence_status(row)["availability"] == "AVAILABLE"
