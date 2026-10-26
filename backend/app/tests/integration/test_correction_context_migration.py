"""Correction context migration on an owned disposable MySQL schema.

The ordinary application database and its data are never used. Old request
rows are inserted using the actual pre-context migration, not inferred models.
"""

from datetime import datetime, timedelta
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.modules.profile_change.models import ProfileChangeRequest
from ..conftest import (
    load_correction_context_migration_module,
    load_profile_change_migration_module,
)


def run_migration(connection, action):
    with Operations.context(MigrationContext.configure(connection)):
        action()
    connection.commit()


@pytest.fixture
def old_schema(mysql_test_engine):
    schema = f"counselconnect_test_{uuid.uuid4().hex}"
    source = mysql_test_engine.url.database
    engine = None
    created = False
    try:
        with mysql_test_engine.connect() as connection:
            connection.execute(text(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
            created = True
            for table in ("users", "cor_screenings", "cor_screening_files"):
                connection.execute(text(f"CREATE TABLE `{schema}`.`{table}` LIKE `{source}`.`{table}`"))
        engine = create_engine(mysql_test_engine.url.set(database=schema), poolclass=NullPool)
        with engine.connect() as connection:
            run_migration(connection, load_profile_change_migration_module().upgrade)
            connection.execute(text("""
                INSERT INTO users (user_id,email,password_hash,role_code,account_status,first_name,last_name)
                VALUES (1,'student@example.test','unused','STUDENT','ACTIVE','Original','Student'),
                       (2,'reviewer@example.test','unused','SUPERADMIN','ACTIVE','Review','Actor')
            """))
            connection.execute(text("""
                INSERT INTO cor_screenings (cor_screening_id,student_user_id,status,format_template_version)
                VALUES (1,1,'PASSED','test')
            """))
            for request_id, status in enumerate(("PENDING", "APPROVED", "REJECTED"), 1):
                connection.execute(text("""
                    INSERT INTO profile_change_requests
                    (change_request_id,student_user_id,cor_screening_id,status,
                     requested_first_name,requested_middle_name,requested_last_name,
                     requested_year_level,requested_section,reviewed_by_user_id,reviewed_at,decision_reason)
                    VALUES (:id,1,1,:status,'Proposed',NULL,'Student',2,'B',:reviewer,:reviewed,:reason)
                """), {"id": request_id, "status": status,
                         "reviewer": None if status == "PENDING" else 2,
                         "reviewed": None if status == "PENDING" else datetime(2026, 10, 24),
                         "reason": "Existing reason" if status == "REJECTED" else None})
            connection.commit()
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with mysql_test_engine.connect() as connection:
                connection.execute(text(f"DROP DATABASE `{schema}`"))


def snapshot(connection, table):
    return [dict(row) for row in connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).mappings()]


@pytest.mark.parametrize("interrupted", [False, True])
def test_upgrade_retry_and_downgrade_preserve_legacy_data(old_schema, interrupted):
    migration = load_correction_context_migration_module()
    with old_schema.connect() as connection:
        before = {table: snapshot(connection, table)
                  for table in ("users", "cor_screenings", "profile_change_requests")}
        if interrupted:
            # Simulate MySQL committing the first ADD COLUMN before an upgrade
            # is interrupted, without applying the remaining migration objects.
            connection.execute(text("ALTER TABLE profile_change_requests ADD COLUMN submission_version INT UNSIGNED NULL"))
            connection.commit()
        run_migration(connection, migration.upgrade)
        run_migration(connection, migration.upgrade)
        after = snapshot(connection, "profile_change_requests")
        assert len(after) == len(before["profile_change_requests"])
        for old, new in zip(before["profile_change_requests"], after):
            assert {key: new[key] for key in old} == old
            assert all(new[key] is None for key in migration.NEW_COLUMNS)
        for table in ("users", "cor_screenings"):
            assert snapshot(connection, table) == before[table]
        columns = {col["name"]: col for col in inspect(connection).get_columns("profile_change_requests")}
        assert all(columns[name]["nullable"] for name in migration.NEW_COLUMNS)
        assert columns["evidence_sha256_hash"]["type"].length == 32
        assert columns["evidence_uploaded_at"]["type"].fsp == 6
        model_columns = set(ProfileChangeRequest.__table__.columns.keys())
        # This historical revision precedes the separate pending-owner guard.
        assert set(columns) == model_columns - {"pending_student_user_id"}
        run_migration(connection, migration.downgrade)
        for table, expected in before.items():
            assert snapshot(connection, table) == expected
        assert not set(migration.NEW_COLUMNS) & {
            col["name"] for col in inspect(connection).get_columns("profile_change_requests")
        }


def new_request(**overrides):
    values = dict(student_user_id=1, cor_screening_id=1, status="PENDING",
                  requested_first_name="Proposed", requested_middle_name=None,
                  requested_last_name="Student", requested_year_level=2, requested_section="B")
    values.update(overrides)
    return ProfileChangeRequest(**values)


def test_context_roundtrip_and_evidence_identity_survives_file_metadata_deletion(old_schema):
    migration = load_correction_context_migration_module()
    with old_schema.connect() as connection:
        run_migration(connection, migration.upgrade)
    uploaded = datetime(2026, 10, 25, 1, 2, 3, 456789)
    extracted = {"first_name": "Original", "middle_name": None, "section": "A"}
    baseline = {**extracted, "year_level": 1, "student_number": "20231234-A"}
    with Session(old_schema) as session:
        session.execute(text("""
            INSERT INTO cor_screening_files
            (cor_screening_file_id,cor_screening_id,storage_key,original_filename,mime_type,
             size_bytes,sha256_hash,uploaded_at,expires_at)
            VALUES (12345,1,'test-private-key','cor.pdf','application/pdf',100,:hash,:uploaded,:expires)
        """), {"hash": b"x" * 32, "uploaded": uploaded, "expires": uploaded + timedelta(days=7)})
        row = new_request(submission_version=1, extracted_values_json=extracted,
                          registered_values_json=baseline, registered_cor_screening_id=1,
                          evidence_file_id=12345, evidence_sha256_hash=b"x" * 32,
                          evidence_uploaded_at=uploaded, evidence_expires_at=uploaded + timedelta(days=7))
        session.add(row)
        session.commit()
        request_id = row.change_request_id
        session.execute(text("DELETE FROM cor_screening_files WHERE cor_screening_file_id = 12345"))
        session.commit()
        session.expire_all()
        saved = session.get(ProfileChangeRequest, request_id)
        assert saved.extracted_values_json == extracted
        assert saved.registered_values_json == baseline
        assert session.scalar(text("SELECT COUNT(*) FROM cor_screening_files")) == 0
        assert saved.evidence_file_id == 12345
        assert saved.evidence_sha256_hash == b"x" * 32
        assert saved.evidence_uploaded_at == uploaded
        assert saved.evidence_expires_at == uploaded + timedelta(days=7)
        assert session.scalar(select(ProfileChangeRequest).where(ProfileChangeRequest.change_request_id == 1)).submission_version is None


def test_lineage_rejects_duplicate_successors_and_versions(old_schema):
    with old_schema.connect() as connection:
        run_migration(connection, load_correction_context_migration_module().upgrade)
    with Session(old_schema) as session:
        root = new_request(status="RETURNED", submission_version=1)
        session.add(root)
        session.flush()
        root_id = root.change_request_id
        child = new_request(status="RETURNED", submission_version=2,
                            previous_change_request_id=root_id, root_change_request_id=root_id)
        session.add(child)
        session.commit()
        child_id = child.change_request_id
        for duplicate in (
            new_request(submission_version=3, previous_change_request_id=root_id, root_change_request_id=root_id),
            new_request(submission_version=2, previous_change_request_id=child_id, root_change_request_id=root_id),
        ):
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
        assert session.get(ProfileChangeRequest, root_id).status == "RETURNED"
        assert session.get(ProfileChangeRequest, child_id).submission_version == 2


@pytest.mark.parametrize("invalid", [
    {"submission_version": 0},
    {"previous_change_request_id": 999999},
    {"root_change_request_id": 999999},
    {"registered_cor_screening_id": 999999},
    {"evidence_uploaded_at": datetime(2026, 10, 25), "evidence_expires_at": datetime(2026, 10, 24)},
])
def test_invalid_context_is_rejected_without_changing_legacy_rows(old_schema, invalid):
    with old_schema.connect() as connection:
        run_migration(connection, load_correction_context_migration_module().upgrade)
    with Session(old_schema) as session:
        session.add(new_request(**invalid))
        with pytest.raises((IntegrityError, OperationalError)):
            session.flush()
        session.rollback()
        assert session.get(ProfileChangeRequest, 1).status == "PENDING"


@pytest.mark.parametrize("new_data", [{"submission_version": 1}, {"status": "RETURNED"},
                                      {"registered_values_json": {"middle_name": None}}])
def test_downgrade_refuses_to_discard_new_context(old_schema, new_data):
    migration = load_correction_context_migration_module()
    with old_schema.connect() as connection:
        run_migration(connection, migration.upgrade)
    with Session(old_schema) as session:
        session.add(new_request(**new_data))
        session.commit()
    with old_schema.connect() as connection:
        before = snapshot(connection, "profile_change_requests")
        with pytest.raises(RuntimeError, match="downgrade refused"):
            run_migration(connection, migration.downgrade)
        assert snapshot(connection, "profile_change_requests") == before
        assert set(migration.NEW_COLUMNS) <= {
            col["name"] for col in inspect(connection).get_columns("profile_change_requests")
        }
