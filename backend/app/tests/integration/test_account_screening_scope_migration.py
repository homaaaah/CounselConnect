"""Account/screening schema defaults and safe rollback on disposable MySQL."""

import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.modules.accounts.models import User
from app.modules.cor_screening.models import CorScreening
from ..conftest import load_account_screening_scope_migration_module


def migrate(connection, action):
    with Operations.context(MigrationContext.configure(connection)):
        action()
    connection.commit()


@pytest.fixture
def before_scope(mysql_test_engine):
    """Copy schema shapes only; remove the two new fields before seeding old rows."""
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
            # CREATE TABLE LIKE renames CHECK constraints. Remove by referenced
            # field to reconstruct the prior schema, independently of downgrade.
            with Operations.context(MigrationContext.configure(connection)) as operations:
                for table, column in (("users", "is_deactivated"), ("cor_screenings", "purpose")):
                    for check in inspect(connection).get_check_constraints(table):
                        if column in check["sqltext"]:
                            operations.drop_constraint(check["name"], table, type_="check")
                    operations.drop_column(table, column)
            roles_and_statuses = (
                ("STUDENT", "PENDING_VERIFICATION"), ("STUDENT", "ACTIVE"),
                ("STUDENT", "VERIFICATION_EXPIRED"), ("COUNSELOR", "ACTIVE"),
                ("GUIDANCE_STAFF", "ACTIVE"), ("SUPERADMIN", "ACTIVE"),
            )
            for user_id, (role, status) in enumerate(roles_and_statuses, 1):
                connection.execute(text("""
                    INSERT INTO users (user_id,email,password_hash,role_code,account_status,first_name,last_name)
                    VALUES (:id,:email,'unused',:role,:status,'Existing','Account')
                """), {"id": user_id, "email": f"scope-{user_id}@example.test", "role": role, "status": status})
            for screening_id, status in enumerate(
                ("PROCESSING", "AWAITING_CONFIRMATION", "PASSED", "NEEDS_RESUBMISSION", "FAILED"), 1
            ):
                connection.execute(text("""
                    INSERT INTO cor_screenings (cor_screening_id,student_user_id,status,format_template_version)
                    VALUES (:id,2,:status,'test')
                """), {"id": screening_id, "status": status})
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


@pytest.mark.parametrize("interrupted_after", [None, "users", "cor_screenings"])
def test_upgrade_retry_and_downgrade_preserve_existing_accounts_and_screenings(before_scope, interrupted_after):
    migration = load_account_screening_scope_migration_module()
    with before_scope.connect() as connection:
        before = {table: snapshot(connection, table) for table in ("users", "cor_screenings")}
        if interrupted_after == "users":
            connection.execute(text("ALTER TABLE users ADD COLUMN is_deactivated BOOL NOT NULL DEFAULT FALSE"))
            connection.commit()
        elif interrupted_after == "cor_screenings":
            connection.execute(text("ALTER TABLE cor_screenings ADD COLUMN purpose VARCHAR(20) NOT NULL DEFAULT 'REGISTRATION'"))
            connection.commit()
        migrate(connection, migration.upgrade)
        migrate(connection, migration.upgrade)
        for table, field, default in (("users", "is_deactivated", 0), ("cor_screenings", "purpose", "REGISTRATION")):
            after = snapshot(connection, table)
            assert len(after) == len(before[table])
            for old, new in zip(before[table], after):
                assert {key: new[key] for key in old} == old
                assert new[field] == default
            columns = {c["name"]: c for c in inspect(connection).get_columns(table)}
            assert not columns[field]["nullable"]
            model = User if table == "users" else CorScreening
            assert set(columns) == set(model.__table__.columns.keys())
        migrate(connection, migration.downgrade)
        for table in before:
            assert snapshot(connection, table) == before[table]
        # Verify the ordinary upgrade can be applied again after a safe rollback.
        migrate(connection, migration.upgrade)


def test_orm_defaults_and_independent_states(before_scope):
    with before_scope.connect() as connection:
        migrate(connection, load_account_screening_scope_migration_module().upgrade)
    with Session(before_scope) as session:
        user = User(email="new@example.test", password_hash="unused", role_code="STUDENT",
                    account_status="PENDING_VERIFICATION", first_name="New", last_name="Student")
        session.add(user)
        session.flush()
        screening = CorScreening(student_user_id=user.user_id, status="PROCESSING", format_template_version="test")
        session.add(screening)
        session.commit()
        session.refresh(user)
        session.refresh(screening)
        assert user.is_deactivated is False
        assert screening.purpose == "REGISTRATION"
        user.is_deactivated = True
        screening.purpose = "CORRECTION"
        session.commit()
        session.expire_all()
        assert user.is_deactivated is True
        assert user.account_status == "PENDING_VERIFICATION"
        assert screening.purpose == "CORRECTION"
        assert screening.status == "PROCESSING"


@pytest.mark.parametrize("statement", [
    "UPDATE users SET is_deactivated = NULL WHERE user_id = 1",
    "UPDATE users SET is_deactivated = 2 WHERE user_id = 1",
    "UPDATE cor_screenings SET purpose = NULL WHERE cor_screening_id = 1",
    "UPDATE cor_screenings SET purpose = 'UNKNOWN' WHERE cor_screening_id = 1",
])
def test_invalid_scope_values_are_rejected(before_scope, statement):
    with before_scope.connect() as connection:
        migrate(connection, load_account_screening_scope_migration_module().upgrade)
        before = {table: snapshot(connection, table) for table in ("users", "cor_screenings")}
        with pytest.raises((IntegrityError, OperationalError)):
            connection.execute(text(statement))
        connection.rollback()
        for table in before:
            assert snapshot(connection, table) == before[table]


@pytest.mark.parametrize("statement", [
    "UPDATE users SET is_deactivated = TRUE WHERE user_id = 1",
    "UPDATE cor_screenings SET purpose = 'CORRECTION' WHERE cor_screening_id = 1",
])
def test_downgrade_refuses_to_erase_restrictions_or_evidence_purpose(before_scope, statement):
    migration = load_account_screening_scope_migration_module()
    with before_scope.connect() as connection:
        migrate(connection, migration.upgrade)
        connection.execute(text(statement))
        connection.commit()
        before = {table: snapshot(connection, table) for table in ("users", "cor_screenings")}
        with pytest.raises(RuntimeError, match="downgrade refused"):
            migrate(connection, migration.downgrade)
        for table in before:
            assert snapshot(connection, table) == before[table]
        assert "is_deactivated" in {c["name"] for c in inspect(connection).get_columns("users")}
        assert "purpose" in {c["name"] for c in inspect(connection).get_columns("cor_screenings")}
