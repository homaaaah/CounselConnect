"""Pending-owner uniqueness on the real MySQL schema, including direct writes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.pool import NullPool

from app.core.exceptions import AppError
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from ..conftest import (
    load_correction_context_migration_module, load_pending_correction_migration_module,
    load_profile_change_migration_module,
)
from .test_correction_context_migration import run_migration, snapshot
from .test_correction_evidence_retention import pending


@pytest.fixture
def before_guard(mysql_test_engine):
    schema = f"counselconnect_test_{uuid.uuid4().hex}"
    source = mysql_test_engine.url.database
    engine = None
    created = False
    try:
        with mysql_test_engine.connect() as connection:
            connection.execute(text(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
            created = True
            for table in ("users", "cor_screenings"):
                connection.execute(text(f"CREATE TABLE `{schema}`.`{table}` LIKE `{source}`.`{table}`"))
        engine = create_engine(mysql_test_engine.url.set(database=schema), poolclass=NullPool)
        with engine.connect() as connection:
            run_migration(connection, load_profile_change_migration_module().upgrade)
            run_migration(connection, load_correction_context_migration_module().upgrade)
            connection.execute(text("""
                INSERT INTO users (user_id,email,password_hash,role_code,account_status,first_name,last_name)
                VALUES (1,'first@example.edu','unused','STUDENT','ACTIVE','First','Student'),
                       (2,'second@example.edu','unused','STUDENT','ACTIVE','Second','Student')
            """))
            connection.execute(text("""
                INSERT INTO cor_screenings (cor_screening_id,student_user_id,status,format_template_version)
                VALUES (1,1,'PASSED','test'), (2,2,'PASSED','test'), (3,1,'PASSED','test')
            """))
            for request_id, owner, screening, status in (
                (1,1,1,"PENDING"), (2,1,1,"APPROVED"), (3,1,1,"RETURNED"),
                (4,1,1,"REJECTED"), (5,2,2,"PENDING"),
            ):
                insert_request(connection, request_id, owner=owner, screening=screening, status=status)
            connection.commit()
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with mysql_test_engine.connect() as connection:
                connection.execute(text(f"DROP DATABASE `{schema}`"))


def insert_request(connection, request_id, *, owner=1, screening=1, status="PENDING"):
    connection.execute(text("""
        INSERT INTO profile_change_requests
        (change_request_id,student_user_id,cor_screening_id,status,requested_first_name,
         requested_middle_name,requested_last_name,requested_year_level,requested_section)
        VALUES (:id,:owner,:screening,:status,'Proposed',NULL,'Student',1,'A')
    """), {"id": request_id, "owner": owner, "screening": screening, "status": status})


@pytest.mark.parametrize("partial", [False, True])
def test_upgrade_retry_downgrade_preserves_rows_and_foreign_keys(before_guard, partial):
    migration = load_pending_correction_migration_module()
    with before_guard.connect() as connection:
        before = snapshot(connection, "profile_change_requests")
        foreign_keys = inspect(connection).get_foreign_keys("profile_change_requests")
        if partial:
            connection.execute(text("""
                ALTER TABLE profile_change_requests ADD COLUMN pending_student_user_id BIGINT UNSIGNED
                GENERATED ALWAYS AS (CASE WHEN status = 'PENDING' THEN student_user_id ELSE NULL END) VIRTUAL
            """))
            connection.commit()
        run_migration(connection, migration.upgrade)
        run_migration(connection, migration.upgrade)
        after = snapshot(connection, "profile_change_requests")
        assert len(after) == len(before)
        for old, new in zip(before, after):
            assert {key: new[key] for key in old} == old
            assert new[migration.COLUMN] == (old["student_user_id"] if old["status"] == "PENDING" else None)
            assert new["submission_version"] is None  # No fabricated legacy versions.
        columns = {c["name"]: c for c in inspect(connection).get_columns("profile_change_requests")}
        assert columns[migration.COLUMN]["computed"]["persisted"] is False
        assert set(columns) == set(ProfileChangeRequest.__table__.columns.keys())
        assert inspect(connection).get_foreign_keys("profile_change_requests") == foreign_keys
        run_migration(connection, migration.downgrade)
        assert snapshot(connection, "profile_change_requests") == before
        assert inspect(connection).get_foreign_keys("profile_change_requests") == foreign_keys
        run_migration(connection, migration.upgrade)


def test_preflight_refuses_ambiguous_pending_rows_without_altering_them(before_guard):
    migration = load_pending_correction_migration_module()
    with before_guard.connect() as connection:
        insert_request(connection, 6)
        connection.commit()
        before = snapshot(connection, "profile_change_requests")
        with pytest.raises(RuntimeError, match="duplicate pending requests exist"):
            run_migration(connection, migration.upgrade)
        assert snapshot(connection, "profile_change_requests") == before
        assert migration.COLUMN not in {c["name"] for c in inspect(connection).get_columns("profile_change_requests")}


@pytest.mark.parametrize("screening", [1, 3])
def test_database_blocks_second_pending_even_in_another_screening(before_guard, screening):
    with before_guard.connect() as connection:
        run_migration(connection, load_pending_correction_migration_module().upgrade)
        with pytest.raises(IntegrityError) as error:
            insert_request(connection, 6, screening=screening)
        assert error.value.orig.args[0] == 1062
        connection.rollback()
        assert connection.scalar(text("SELECT COUNT(*) FROM profile_change_requests WHERE student_user_id=1 AND status='PENDING'")) == 1


@pytest.mark.parametrize("status", ["APPROVED", "RETURNED", "REJECTED"])
def test_terminal_status_automatically_releases_owner_slot(before_guard, status):
    with before_guard.connect() as connection:
        run_migration(connection, load_pending_correction_migration_module().upgrade)
        connection.execute(text("UPDATE profile_change_requests SET status=:status WHERE change_request_id=1"), {"status": status})
        insert_request(connection, 6)
        connection.commit()
        assert connection.scalar(text("SELECT pending_student_user_id FROM profile_change_requests WHERE change_request_id=1")) is None
        assert connection.scalar(text("SELECT pending_student_user_id FROM profile_change_requests WHERE change_request_id=6")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM profile_change_requests WHERE student_user_id=1")) == 5


def test_derived_guard_cannot_be_bypassed_with_null(before_guard):
    with before_guard.connect() as connection:
        run_migration(connection, load_pending_correction_migration_module().upgrade)
        with pytest.raises((IntegrityError, OperationalError)):
            connection.execute(text("""
                INSERT INTO profile_change_requests
                (student_user_id,cor_screening_id,status,requested_first_name,requested_last_name,
                 requested_year_level,requested_section,pending_student_user_id)
                VALUES (1,1,'PENDING','Proposed','Student',1,'A',NULL)
            """))
        connection.rollback()
        assert connection.scalar(text("SELECT COUNT(*) FROM profile_change_requests WHERE status='PENDING'")) == 2


def test_simultaneous_direct_submissions_have_one_winner(before_guard):
    with before_guard.connect() as connection:
        run_migration(connection, load_pending_correction_migration_module().upgrade)
        connection.execute(text("UPDATE profile_change_requests SET status='RETURNED' WHERE change_request_id=1"))
        connection.commit()
    start = Barrier(2)

    def submit(request_id):
        try:
            with before_guard.begin() as connection:
                start.wait(timeout=5)
                insert_request(connection, request_id)
            return "created"
        except IntegrityError as error:
            assert error.orig.args[0] == 1062
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, (10, 11)))
    assert sorted(results) == ["created", "duplicate"]
    with before_guard.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM profile_change_requests WHERE student_user_id=1 AND status='PENDING'")) == 1


def test_constraint_conflict_maps_to_safe_pending_error(db_session, academic_references, monkeypatch):
    _service, user, _screening, _profile, request, _evidence, path = pending(db_session, academic_references, monkeypatch)
    reviews = ProfileChangeService(db_session)
    # Force the database fallback to prove that safety does not depend on a
    # successful pre-check (production also holds the Student lock).
    monkeypatch.setattr(reviews.repository, "find_pending_for_student", lambda owner: None)
    with pytest.raises(AppError) as error:
        reviews.create_pending(user, request.cor_screening_id, first_name="Private proposal", middle_name=None,
                               last_name="Student", year_level=1, section="Different")
    assert error.value.code == "CHANGE_REQUEST_PENDING"
    assert error.value.status_code == 409
    assert error.value.details == {}
    assert "Private proposal" not in error.value.message
    assert "uq_profile" not in error.value.message
    assert db_session.is_active
    db_session.refresh(request)
    assert request.status == "PENDING"
    assert request.requested_section == "B"
    assert path.exists()
