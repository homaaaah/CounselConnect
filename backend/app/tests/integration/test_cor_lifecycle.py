"""COR privacy and decision races against the disposable MySQL schema."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, current_thread

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.accounts.models import User
from app.modules.enrollment_verification.models import (
    EnrollmentVerification,
    EnrollmentVerificationFile,
)
from app.modules.enrollment_verification.service import EnrollmentVerificationService


@pytest.fixture()
def people(db_session):
    student = User(
        email="cor-student@example.edu",
        password_hash="unused",
        role_code="STUDENT",
        account_status="PENDING_VERIFICATION",
        first_name="Ana",
        last_name="Santos",
    )
    counselor = User(
        email="cor-counselor@example.edu",
        password_hash="unused",
        role_code="COUNSELOR",
        account_status="ACTIVE",
        first_name="Cora",
        last_name="Reyes",
    )
    db_session.add_all([student, counselor])
    db_session.flush()
    return student, counselor


@pytest.fixture()
def pending(db_session, people):
    student, counselor = people
    service = EnrollmentVerificationService(db_session)
    verification = service.submit_cor(student.user_id, b"%PDF-1.4 test", "cor.pdf")
    row = service.repository.find_active_file(verification.verification_id)
    return service, verification, row, student, counselor


def test_failed_decision_cleanup_is_tracked_and_retried(
    pending, monkeypatch, db_session
):
    service, verification, row, student, counselor = pending
    path = service._storage_path(row.storage_key)
    file_id = row.file_id
    with monkeypatch.context() as patch:
        patch.setattr(service, "_delete_cor_bytes", lambda _: False)
        result, _ = service.approve(verification.verification_id, counselor.user_id)
    assert result.status == "APPROVED" and student.account_status == "ACTIVE"
    assert path.exists()
    assert db_session.get(EnrollmentVerificationFile, file_id).cleanup_state == "FAILED"
    service.cleanup_due_files()
    assert not path.exists()
    assert db_session.get(EnrollmentVerificationFile, file_id) is None


def test_rejection_deletes_file_and_keeps_account_restricted(pending, db_session):
    service, verification, row, student, counselor = pending
    path = service._storage_path(row.storage_key)
    file_id = row.file_id
    service.reject(
        verification.verification_id, counselor.user_id, "Please contact the office."
    )
    assert student.account_status == "PENDING_VERIFICATION"
    assert verification.status == "REJECTED"
    assert not path.exists()
    assert db_session.get(EnrollmentVerificationFile, file_id) is None


@pytest.mark.parametrize("action", ["preview", "approve", "cleanup"])
def test_expiry_blocks_reads_decisions_and_runs_without_requests(
    pending, db_session, action
):
    service, verification, row, student, counselor = pending
    path = service._storage_path(row.storage_key)
    verification.submitted_at = datetime.now(timezone.utc) - timedelta(days=8)
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()
    if action == "cleanup":
        service.cleanup_due_files()
    else:
        with pytest.raises(AppError) as caught:
            if action == "preview":
                service.read_cor_pdf(verification.verification_id)
            else:
                service.approve(verification.verification_id, counselor.user_id)
        assert caught.value.code == "VERIFICATION_EXPIRED"
        db_session.rollback()  # same behavior as the failed request dependency
    db_session.refresh(verification)
    assert verification.status == "EXPIRED"
    assert student.account_status == "PENDING_VERIFICATION"
    assert not path.exists()


def test_replacement_failure_preserves_old_retry_record_and_new_file(
    pending, monkeypatch, db_session
):
    service, verification, old, student, _ = pending
    old_id, old_key, deadline = old.file_id, old.storage_key, old.expires_at
    with monkeypatch.context() as patch:
        patch.setattr(service, "_delete_cor_bytes", lambda _: False)
        replacement = service.submit_cor(
            student.user_id, b"%PDF-1.4 replacement", "cor.pdf"
        )
    active = service.repository.find_active_file(verification.verification_id)
    assert replacement.verification_id == verification.verification_id
    assert active.storage_key != old_key and active.expires_at == deadline
    assert db_session.get(EnrollmentVerificationFile, old_id).cleanup_state == "FAILED"
    service.cleanup_due_files()
    assert not service._storage_path(old_key).exists()
    assert service.read_cor_pdf(verification.verification_id) == b"%PDF-1.4 replacement"


def test_decision_commit_failure_does_not_delete_evidence(
    pending, monkeypatch, db_session
):
    service, verification, row, _, counselor = pending
    path = service._storage_path(row.storage_key)
    with monkeypatch.context() as patch:

        def fail():
            raise RuntimeError("simulated commit failure")

        patch.setattr(db_session, "commit", fail)
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            service.approve(verification.verification_id, counselor.user_id)
    db_session.rollback()
    db_session.refresh(verification)
    assert verification.status == "PENDING"
    assert path.exists()


def test_cleanup_enforces_original_deadline_even_for_legacy_replacements(
    pending, db_session
):
    service, verification, row, _, _ = pending
    path = service._storage_path(row.storage_key)
    verification.submitted_at = datetime.now(timezone.utc) - timedelta(days=8)
    row.expires_at = datetime.now(timezone.utc) + timedelta(days=6)
    db_session.commit()
    service.cleanup_due_files()
    assert verification.status == "EXPIRED"
    assert not path.exists()


@pytest.mark.parametrize("first_action", ["approve", "reject"])
def test_concurrent_decisions_have_only_one_winner(mysql_test_engine, first_action):
    """Hold the first row lock while another connection attempts a decision."""
    import uuid

    suffix = uuid.uuid4().hex
    with Session(mysql_test_engine, expire_on_commit=False) as session:
        student = User(
            email=f"race-student-{suffix}@example.edu",
            password_hash="unused",
            role_code="STUDENT",
            account_status="PENDING_VERIFICATION",
            first_name="Ana",
            last_name="Santos",
        )
        counselor = User(
            email=f"race-counselor-{suffix}@example.edu",
            password_hash="unused",
            role_code="COUNSELOR",
            account_status="ACTIVE",
            first_name="Cora",
            last_name="Reyes",
        )
        session.add_all([student, counselor])
        session.flush()
        service = EnrollmentVerificationService(session)
        verification = service.submit_cor(student.user_id, b"%PDF-race", "cor.pdf")
        verification_id, student_id, counselor_id = (
            verification.verification_id,
            student.user_id,
            counselor.user_id,
        )

    locked, release, competing = Event(), Event(), Event()

    def before_execute(conn, cursor, statement, parameters, context, executemany):
        if (
            current_thread().name.endswith("_1")
            and "FOR UPDATE" in statement
            and "users" in statement
        ):
            competing.set()

    def decide(first):
        with Session(mysql_test_engine, expire_on_commit=False) as session:
            service = EnrollmentVerificationService(session)
            if first:
                require_cor = service._require_current_cor

                def wait_while_locked(verification):
                    require_cor(verification)
                    locked.set()
                    assert release.wait(10), "First decision was not released"

                service._require_current_cor = wait_while_locked
            action = (
                first_action
                if first
                else ("reject" if first_action == "approve" else "approve")
            )
            try:
                if action == "approve":
                    service.approve(verification_id, counselor_id)
                else:
                    service.reject(verification_id, counselor_id, "Reviewed")
                return action
            except AppError as error:
                session.rollback()
                return error.code

    event.listen(mysql_test_engine, "before_cursor_execute", before_execute)
    try:
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="review-race"
        ) as executor:
            first = executor.submit(decide, True)
            try:
                assert locked.wait(10)
                second = executor.submit(decide, False)
                assert competing.wait(10)
            finally:
                release.set()
            assert first.result(timeout=10) == first_action
            assert second.result(timeout=10) == "DECISION_ALREADY_MADE"
    finally:
        event.remove(mysql_test_engine, "before_cursor_execute", before_execute)
    with Session(mysql_test_engine) as session:
        result = session.get(EnrollmentVerification, verification_id)
        user = session.get(User, student_id)
        assert result.status == (
            "APPROVED" if first_action == "approve" else "REJECTED"
        )
        assert user.account_status == (
            "ACTIVE" if first_action == "approve" else "PENDING_VERIFICATION"
        )
        assert (result.valid_until is not None) == (first_action == "approve")
        assert (
            session.scalar(
                select(EnrollmentVerificationFile).where(
                    EnrollmentVerificationFile.verification_id == verification_id
                )
            )
            is None
        )
