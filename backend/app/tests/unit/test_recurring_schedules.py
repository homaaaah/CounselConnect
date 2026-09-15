"""MySQL persistence coverage for recurring schedules and temporary blocks."""

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import AppError
from app.modules.accounts.models import Campus, User
from app.modules.appointments.models import (
    Appointment,
    AvailabilitySlot,
    CounselorAvailabilityBlock,
    CounselorWeeklySchedule,
)
from app.modules.appointments.repository import AppointmentsRepository
from app.modules.appointments.schemas import (
    AppointmentCreateRequest,
    AvailabilityBlockCreateRequest,
)
from app.modules.appointments.service import AppointmentsService

from ..conftest import load_recurring_schedules_migration_module


def check_error(code, fn):
    with pytest.raises(AppError) as exc:
        fn()
    assert exc.value.code == code


@pytest.fixture()
def counselor_and_campus(db_session):
    suffix = "recurring"
    counselor = User(email=f"{suffix}@example.edu", password_hash="placeholder", role_code="COUNSELOR", account_status="ACTIVE", first_name="Cora", last_name="Counselor")
    campus = Campus(campus_name="Recurring Campus", guidance_office_location="Office 101")
    db_session.add_all([counselor, campus])
    db_session.flush()
    return counselor, campus


def schedule_values(counselor, campus, **overrides):
    values = dict(counselor_user_id=counselor.user_id, campus_id=campus.campus_id, day_of_week=1, start_time=time(8), end_time=time(10), slot_duration_minutes=30, delivery_mode="BOTH")
    values.update(overrides)
    return values


def test_migration_shape_and_downgrade_preserves_existing_slots(mysql_test_engine):
    """Downgrade/re-upgrade run in a private schema; shared schema stays untouched."""
    from ..conftest import (
        BASELINE_SQL,
        RECURRING_SCHEDULES_MIGRATION_FILE,
        _test_url,
        load_migration_module,
        load_blocked_dates_migration_module,
    )
    import re as _re
    import uuid as _uuid
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    from pymysql.constants import CLIENT

    migration = load_recurring_schedules_migration_module()
    url = _test_url()
    schema = f"counselconnect_test_{_uuid.uuid4().hex}"
    assert _re.fullmatch(r"counselconnect_test_[0-9a-f]{32}", schema)
    admin = create_engine(url.set(database="mysql"), poolclass=NullPool, connect_args={"connect_timeout": 5})
    engine = None
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
            created = True
        engine = create_engine(
            url.set(database=schema),
            poolclass=NullPool,
            connect_args={"client_flag": CLIENT.MULTI_STATEMENTS, "init_command": "SET time_zone = '+00:00'"},
        )
        sql = BASELINE_SQL.read_text(encoding="utf-8")
        assert sql.count("CREATE DATABASE IF NOT EXISTS counselconnect") == 1
        assert sql.count("USE counselconnect;") == 1
        sql = sql.replace("CREATE DATABASE IF NOT EXISTS counselconnect", f"CREATE DATABASE IF NOT EXISTS `{schema}`")
        sql = sql.replace("USE counselconnect;", f"USE `{schema}`;")
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute(sql)
                while cursor.nextset():
                    pass
            raw.commit()
        finally:
            raw.close()
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                load_migration_module().upgrade()
                load_blocked_dates_migration_module().upgrade()
                load_recurring_schedules_migration_module().upgrade()
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO campuses (campus_name, guidance_office_location, is_active) VALUES ('Migration Campus', 'Office 1', TRUE)"))
            conn.execute(text("INSERT INTO users (email, password_hash, role_code, account_status, first_name, last_name) VALUES ('migration-counselor@example.edu', 'placeholder', 'COUNSELOR', 'ACTIVE', 'Cora', 'Counselor'), ('migration-student@example.edu', 'placeholder', 'STUDENT', 'ACTIVE', 'Stu', 'Dent')"))
            counselor_id = conn.execute(text("SELECT user_id FROM users WHERE email = 'migration-counselor@example.edu'")).scalar()
            student_id = conn.execute(text("SELECT user_id FROM users WHERE email = 'migration-student@example.edu'")).scalar()
            campus_id = conn.execute(text("SELECT campus_id FROM campuses WHERE campus_name = 'Migration Campus'")).scalar()
            conn.execute(text(f"INSERT INTO availability_slots (counselor_user_id, campus_id, delivery_mode, starts_at, ends_at, status) VALUES ({counselor_id}, {campus_id}, 'ONLINE', '2099-01-01 00:00:00', '2099-01-01 01:00:00', 'RESERVED')"))
            conn.execute(text(f"INSERT INTO appointments (student_user_id, counselor_user_id, availability_slot_id, appointment_mode, status) SELECT {student_id}, {counselor_id}, slot_id, 'ONLINE', 'PENDING' FROM availability_slots WHERE counselor_user_id = {counselor_id} LIMIT 1"))
            conn.commit()
            tables_before = set(inspect(conn).get_table_names())
            assert {"counselor_weekly_schedules", "counselor_availability_blocks"} <= tables_before
            assert "weekly_schedule_id" in {column["name"] for column in inspect(conn).get_columns("availability_slots")}
            assert "fk_availability_weekly_schedule" in {fk["name"] for fk in inspect(conn).get_foreign_keys("availability_slots")}
            assert "idx_availability_weekly_schedule" in {index["name"] for index in inspect(conn).get_indexes("availability_slots")}
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                migration.downgrade()
            tables_after = set(inspect(conn).get_table_names())
            assert "counselor_weekly_schedules" not in tables_after
            assert "counselor_availability_blocks" not in tables_after
            assert "availability_slots" in tables_after
            assert conn.scalar(text("SELECT COUNT(*) FROM availability_slots")) == 1
            assert conn.scalar(text("SELECT COUNT(*) FROM appointments")) == 1
            with Operations.context(ctx):
                migration.upgrade()
            # Re-upgrade restores the structures and preserves existing rows.
            tables_reupgraded = set(inspect(conn).get_table_names())
            assert {"counselor_weekly_schedules", "counselor_availability_blocks"} <= tables_reupgraded
            assert "weekly_schedule_id" in {column["name"] for column in inspect(conn).get_columns("availability_slots")}
            assert conn.scalar(text("SELECT COUNT(*) FROM availability_slots")) == 1
            assert conn.scalar(text("SELECT COUNT(*) FROM appointments")) == 1
            assert conn.scalar(text("SELECT weekly_schedule_id FROM availability_slots")) is None
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as conn:
                conn.execute(text(f"DROP DATABASE `{schema}`"))
        admin.dispose()


def test_weekly_schedule_constraints_and_optional_slot_reference(db_session, counselor_and_campus):
    counselor, campus = counselor_and_campus
    schedule = CounselorWeeklySchedule(**schedule_values(counselor, campus))
    db_session.add(schedule)
    db_session.flush()
    slot = AvailabilitySlot(counselor_user_id=counselor.user_id, campus_id=campus.campus_id, delivery_mode="BOTH", starts_at=datetime(2099, 1, 5, 0, tzinfo=timezone.utc), ends_at=datetime(2099, 1, 5, 0, 30, tzinfo=timezone.utc), weekly_schedule_id=None)
    db_session.add(slot)
    db_session.flush()
    assert slot.weekly_schedule_id is None

    for invalid in (
        {"day_of_week": 0},
        {"end_time": time(8)},
        {"slot_duration_minutes": 10},
        {"delivery_mode": "PHONE"},
    ):
        with db_session.begin_nested():
            db_session.add(CounselorWeeklySchedule(**schedule_values(counselor, campus, **invalid)))
            with pytest.raises(DBAPIError):
                db_session.flush()


def test_weekly_schedule_foreign_key_and_exact_duplicate(db_session, counselor_and_campus):
    counselor, campus = counselor_and_campus
    db_session.add(CounselorWeeklySchedule(**schedule_values(counselor, campus)))
    db_session.flush()
    with db_session.begin_nested():
        db_session.add(CounselorWeeklySchedule(**schedule_values(counselor, campus)))
        with pytest.raises(DBAPIError):
            db_session.flush()
    with db_session.begin_nested():
        db_session.add(CounselorWeeklySchedule(**schedule_values(counselor, campus, counselor_user_id=999999)))
        with pytest.raises(DBAPIError):
            db_session.flush()
    with db_session.begin_nested():
        db_session.add(CounselorWeeklySchedule(**schedule_values(counselor, campus, campus_id=999999)))
        with pytest.raises(DBAPIError):
            db_session.flush()
    with db_session.begin_nested():
        db_session.add(AvailabilitySlot(
            counselor_user_id=counselor.user_id,
            campus_id=campus.campus_id,
            delivery_mode="ONLINE",
            starts_at=datetime(2099, 1, 6, tzinfo=timezone.utc),
            ends_at=datetime(2099, 1, 6, 1, tzinfo=timezone.utc),
            weekly_schedule_id=999999,
        ))
        with pytest.raises(DBAPIError):
            db_session.flush()


def test_blocks_and_overlap_repository_operations(db_session, counselor_and_campus):
    counselor, campus = counselor_and_campus
    repo = AppointmentsRepository(db_session)
    start = datetime(2099, 1, 5, 1, tzinfo=timezone.utc)
    block = repo.create_availability_block(counselor_user_id=counselor.user_id, starts_at=start, ends_at=start + timedelta(hours=2), is_all_day=False, reason="Training")
    db_session.flush()
    assert repo.overlapping_availability_blocks(counselor.user_id, start + timedelta(minutes=30), start + timedelta(hours=3)) == [block]
    with db_session.begin_nested():
        db_session.add(CounselorAvailabilityBlock(counselor_user_id=counselor.user_id, starts_at=start, ends_at=start + timedelta(hours=2), is_all_day=False))
        with pytest.raises(DBAPIError):
            db_session.flush()
    with db_session.begin_nested():
        db_session.add(CounselorAvailabilityBlock(counselor_user_id=counselor.user_id, starts_at=start, ends_at=start, is_all_day=False))
        with pytest.raises(DBAPIError):
            db_session.flush()

    student = User(email="recurring-student@example.edu", password_hash="placeholder", role_code="STUDENT", account_status="ACTIVE", first_name="Stu", last_name="Dent")
    slot = AvailabilitySlot(counselor_user_id=counselor.user_id, campus_id=campus.campus_id, delivery_mode="ONLINE", starts_at=start, ends_at=start + timedelta(hours=1))
    db_session.add_all([student, slot])
    db_session.flush()
    appointment = Appointment(student_user_id=student.user_id, counselor_user_id=counselor.user_id, availability_slot_id=slot.slot_id, appointment_mode="ONLINE", status="PENDING")
    db_session.add(appointment)
    db_session.flush()
    assert repo.overlapping_active_appointments(counselor.user_id, start + timedelta(minutes=15), start + timedelta(minutes=45)) == [appointment]
    appointment.status = "COMPLETED"
    db_session.flush()
    assert repo.overlapping_active_appointments(counselor.user_id, start, start + timedelta(hours=1)) == []


def test_models_match_migrated_metadata(mysql_test_engine):
    inspector = inspect(mysql_test_engine)
    assert {column["name"] for column in inspector.get_columns("counselor_weekly_schedules")} >= {
        "weekly_schedule_id", "counselor_user_id", "campus_id", "day_of_week",
        "start_time", "end_time", "slot_duration_minutes", "delivery_mode",
        "is_active", "created_at", "updated_at",
    }
    assert CounselorWeeklySchedule.__table__.name == "counselor_weekly_schedules"
    assert CounselorAvailabilityBlock.__table__.name == "counselor_availability_blocks"
    assert AvailabilitySlot.__table__.c.weekly_schedule_id.nullable is True


# ---------------------------------------------------------------------------
# Service-boundary invariants (booking/search vs. blocks; blocks vs. appointments)
# ---------------------------------------------------------------------------


def _service_actor(role, index):
    return type("Actor", (), {"user_id": index, "role_code": role, "account_status": "ACTIVE"})()


@pytest.fixture()
def service_counselor(db_session):
    counselor = User(email=f"block-service-{uuid4().hex}@example.edu", password_hash="placeholder", role_code="COUNSELOR", account_status="ACTIVE", first_name="Cora", last_name="Blocks")
    campus = Campus(campus_name="Block Service Campus", guidance_office_location="Office 9")
    student = User(email=f"block-student-{uuid4().hex}@example.edu", password_hash="placeholder", role_code="STUDENT", account_status="ACTIVE", first_name="Stu", last_name="Blocks")
    db_session.add_all([counselor, campus, student])
    db_session.flush()
    return counselor, campus, student


def test_booking_rejected_inside_availability_block(db_session, service_counselor):
    counselor, campus, student = service_counselor
    start = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
    slot = AvailabilitySlot(counselor_user_id=counselor.user_id, campus_id=campus.campus_id, delivery_mode="ONLINE", starts_at=start, ends_at=start + timedelta(hours=1), status="AVAILABLE")
    block = CounselorAvailabilityBlock(counselor_user_id=counselor.user_id, starts_at=start + timedelta(minutes=15), ends_at=start + timedelta(minutes=45), is_all_day=False)
    db_session.add_all([slot, block])
    db_session.flush()
    service = AppointmentsService(db_session)
    check_error(
        "SLOT_UNAVAILABLE",
        lambda: service.book(
            _service_actor("STUDENT", student.user_id),
            AppointmentCreateRequest(availability_slot_id=slot.slot_id, appointment_mode="ONLINE"),
        ),
    )
    # The block must not mutate the slot or create any appointment for this student.
    db_session.refresh(slot)
    db_session.expire_all()
    assert slot.status == "AVAILABLE"
    assert db_session.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.student_user_id == student.user_id)
    ) == 0


def test_slot_search_excludes_availability_blocks(db_session, service_counselor):
    counselor, campus, student = service_counselor
    start = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
    slots = [
        AvailabilitySlot(counselor_user_id=counselor.user_id, campus_id=campus.campus_id, delivery_mode="ONLINE", starts_at=start + timedelta(hours=i), ends_at=start + timedelta(hours=i + 1), status="AVAILABLE")
        for i in range(3)
    ]
    block = CounselorAvailabilityBlock(counselor_user_id=counselor.user_id, starts_at=start + timedelta(minutes=30), ends_at=start + timedelta(hours=2), is_all_day=False)
    db_session.add_all([*slots, block])
    db_session.flush()
    service = AppointmentsService(db_session)
    result = service.list_slots(_service_actor("STUDENT", student.user_id))
    listed_ids = {s.slot_id for s in result["items"]}
    assert slots[0].slot_id not in listed_ids
    assert slots[1].slot_id not in listed_ids
    assert slots[2].slot_id in listed_ids


def test_block_rejected_overlapping_active_appointment_and_never_mutates_it(db_session, service_counselor):
    counselor, campus, student = service_counselor
    start = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
    slot = AvailabilitySlot(counselor_user_id=counselor.user_id, campus_id=campus.campus_id, delivery_mode="ONLINE", starts_at=start, ends_at=start + timedelta(hours=1), status="RESERVED")
    db_session.add(slot)
    db_session.flush()
    appointment = Appointment(student_user_id=student.user_id, counselor_user_id=counselor.user_id, availability_slot_id=slot.slot_id, appointment_mode="ONLINE", status="PENDING")
    db_session.add(appointment)
    db_session.flush()
    service = AppointmentsService(db_session)
    check_error(
        "BLOCK_CONFLICT",
        lambda: service.create_availability_block(
            _service_actor("COUNSELOR", counselor.user_id),
            AvailabilityBlockCreateRequest(
                starts_at=(start + timedelta(minutes=20)).replace(tzinfo=timezone.utc),
                ends_at=(start + timedelta(minutes=50)).replace(tzinfo=timezone.utc),
                is_all_day=False,
            ),
        ),
    )
    db_session.expire_all()
    assert appointment.status == "PENDING"
    assert slot.status == "RESERVED"
    assert db_session.scalar(
        select(func.count()).select_from(CounselorAvailabilityBlock).where(CounselorAvailabilityBlock.counselor_user_id == counselor.user_id)
    ) == 0
