"""Scheduling state, mode, ownership and MySQL transaction regressions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.modules.accounts.models import Campus, StudentProfile, User
from app.modules.appointments.models import Appointment, AvailabilitySlot
from app.modules.appointments.schemas import (
    AvailabilitySlotCreateRequest,
    AppointmentCreateRequest,
)
from app.modules.appointments.service import AppointmentsService
from app.modules.audit.models import AuditEvent
from app.modules.messaging.models import Conversation


@pytest.fixture()
def actors(db_session, academic_references):
    campus_id, program_id = academic_references
    campus = db_session.get(Campus, campus_id)
    campus.guidance_office_location = "Guidance Office, Room 201"
    users = []
    for i, role in enumerate(
        ["COUNSELOR", "COUNSELOR", "STUDENT", "STUDENT", "GUIDANCE_STAFF"]
    ):
        user = User(
            email=f"scheduling-{i}@example.edu",
            password_hash=hash_password("synthetic-test-pass"),
            first_name=f"Test{i}",
            last_name="Scheduling",
            role_code=role,
            account_status="ACTIVE",
        )
        db_session.add(user)
        db_session.flush()
        if role == "STUDENT":
            db_session.add(
                StudentProfile(
                    user_id=user.user_id,
                    student_number=f"APPT-{i}",
                    campus_id=campus_id,
                    program_id=program_id,
                    year_level=1,
                    section="A",
                )
            )
        users.append(user)
    db_session.flush()
    return users, campus


def create_slot(service, counselor, campus, mode="BOTH", offset=0):
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(
        days=2, hours=offset
    )
    data = AvailabilitySlotCreateRequest(
        campus_id=campus.campus_id,
        delivery_mode=mode,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        slot_duration_minutes=60,
    )
    return service.create_slots(counselor, data)[0]


def book(service, student, slot, mode="ONLINE"):
    return service.book(
        student,
        AppointmentCreateRequest(
            availability_slot_id=slot.slot_id, appointment_mode=mode
        ),
    )


def check_error(code, fn):
    with pytest.raises(AppError) as exc:
        fn()
    assert exc.value.code == code


def check_error_message(code, message, fn):
    with pytest.raises(AppError) as exc:
        fn()
    assert exc.value.code == code
    assert exc.value.message == message


@pytest.mark.parametrize(
    "supported,selected,allowed",
    [
        ("ONLINE", "ONLINE", True),
        ("ONLINE", "FACE_TO_FACE", False),
        ("FACE_TO_FACE", "ONLINE", False),
        ("FACE_TO_FACE", "FACE_TO_FACE", True),
        ("BOTH", "ONLINE", True),
        ("BOTH", "FACE_TO_FACE", True),
    ],
)
def test_modes_and_location_snapshot(db_session, actors, supported, selected, allowed):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus, supported)
    if not allowed:
        check_error("MODE_INCOMPATIBLE", lambda: book(svc, users[2], slot, selected))
        assert svc.repository.find_slot(slot.slot_id).status == "AVAILABLE"
        return
    appt = book(svc, users[2], slot, selected)
    assert appt.status == "PENDING"
    assert svc.repository.find_slot(slot.slot_id).status == "RESERVED"
    assert appt.meeting_location == (
        campus.guidance_office_location if selected == "FACE_TO_FACE" else None
    )
    svc.accounts.set_guidance_office_location(users[0], campus.campus_id, "New office")
    assert (
        svc.detail(users[2], appt.appointment_id).meeting_location
        == appt.meeting_location
    )
    assert appt.model_dump(mode="json")["starts_at"].endswith("Z")


def _past_slot(db_session, counselor, campus, *, days, hours=0):
    """Insert an AVAILABLE slot whose scheduled start is already past."""
    start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        days=days, hours=hours
    )
    slot = AvailabilitySlot(
        counselor_user_id=counselor.user_id,
        campus_id=campus.campus_id,
        delivery_mode="BOTH",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status="AVAILABLE",
    )
    db_session.add(slot)
    db_session.flush()
    return slot


def test_booking_rejected_for_past_date(db_session, actors):
    from app.modules.appointments.service import manila_today
    from zoneinfo import ZoneInfo

    users, campus = actors
    svc = AppointmentsService(db_session)
    # The slot start maps to a Manila date strictly before today's Manila date.
    slot = _past_slot(db_session, users[0], campus, days=1)
    manila_slot_date = slot.starts_at.replace(tzinfo=timezone.utc).astimezone(
        ZoneInfo("Asia/Manila")
    ).date()
    assert manila_slot_date < manila_today()
    check_error_message(
        "APPOINTMENT_DATE_PASSED",
        "This appointment date has already passed. Please select another available date.",
        lambda: book(svc, users[2], slot),
    )
    assert svc.repository.find_slot(slot.slot_id).status == "AVAILABLE"


def test_booking_rejected_for_passed_time_today(db_session, actors):
    from app.modules.appointments.service import manila_today
    from zoneinfo import ZoneInfo

    users, campus = actors
    svc = AppointmentsService(db_session)
    # Earlier today in Manila (a slot start that is past UTC-now but whose
    # Manila date is still today, which holds whenever Manila is ahead of UTC).
    start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    slot = AvailabilitySlot(
        counselor_user_id=users[0].user_id,
        campus_id=campus.campus_id,
        delivery_mode="BOTH",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status="AVAILABLE",
    )
    db_session.add(slot)
    db_session.flush()
    manila_slot_date = slot.starts_at.replace(tzinfo=timezone.utc).astimezone(
        ZoneInfo("Asia/Manila")
    ).date()
    if manila_slot_date < manila_today():
        pytest.skip("Manila already rolled to the next day for this slot time")
    check_error_message(
        "APPOINTMENT_TIME_PASSED",
        "This appointment time is no longer available. Please select another available time.",
        lambda: book(svc, users[2], slot),
    )
    assert svc.repository.find_slot(slot.slot_id).status == "AVAILABLE"


def test_reschedule_rejected_for_past_replacement(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    first = create_slot(svc, users[0], campus)
    appt = book(svc, users[2], first)
    svc.transition(users[0], appt.appointment_id, "confirm")
    past = _past_slot(db_session, users[0], campus, days=1)
    data = AppointmentCreateRequest(
        availability_slot_id=past.slot_id, appointment_mode="ONLINE"
    )
    check_error(
        "APPOINTMENT_DATE_PASSED",
        lambda: svc.reschedule(users[2], appt.appointment_id, data),
    )
    # The original reservation stays intact after the failed replacement.
    assert svc.repository.find_slot(first.slot_id).status == "RESERVED"
    assert svc.repository.find_slot(past.slot_id).status == "AVAILABLE"


def test_calendar_marks_past_days_and_clamps_today_times(db_session, actors):
    from zoneinfo import ZoneInfo

    from app.modules.appointments.service import manila_today

    users, campus = actors
    svc = AppointmentsService(db_session)
    today = manila_today()
    start = today - timedelta(days=2)
    calendar = svc.calendar(users[2], start, today + timedelta(days=1))
    days = {day["calendar_date"]: day for day in calendar["days"]}
    # Fully past days are flagged and carry no available times.
    assert days[start]["is_past"] is True
    assert days[start]["available_times"] == []
    # Future days are untouched: full default times on a weekday.
    future = today + timedelta(days=1)
    if future.weekday() < 5:
        assert days[future]["is_past"] is False
        assert days[future]["available_times"] == [
            f"{hour:02d}:00" for hour in range(8, 16)
        ]
    # Today keeps only times whose Manila hour is still ahead of now.
    now_manila = datetime.now(ZoneInfo("Asia/Manila"))
    if today.weekday() < 5:
        expected_today = [
            f"{hour:02d}:00"
            for hour in range(8, 16)
            if now_manila.replace(hour=hour, minute=0, second=0, microsecond=0)
            > now_manila
        ]
        assert days[today]["is_past"] is False
        assert days[today]["available_times"] == expected_today


def test_location_required_at_creation_and_booking(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    campus.guidance_office_location = None
    db_session.flush()
    for mode in ["FACE_TO_FACE", "BOTH"]:
        check_error(
            "GUIDANCE_OFFICE_REQUIRED", lambda: create_slot(svc, users[0], campus, mode)
        )
    slot = create_slot(svc, users[0], campus, "ONLINE")
    assert slot.delivery_mode == "ONLINE"
    svc.accounts.set_guidance_office_location(users[0], campus.campus_id, "Room 2")
    ftf = create_slot(svc, users[0], campus, "BOTH", 2)
    campus.guidance_office_location = None
    db_session.flush()
    check_error(
        "GUIDANCE_OFFICE_REQUIRED", lambda: book(svc, users[2], ftf, "FACE_TO_FACE")
    )


def test_conflicts_and_release(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    first = create_slot(svc, users[0], campus)
    check_error("SCHEDULE_CONFLICT", lambda: create_slot(svc, users[0], campus))
    another = create_slot(svc, users[1], campus)
    appt = book(svc, users[2], first)
    check_error("SLOT_UNAVAILABLE", lambda: book(svc, users[3], first))
    check_error("SCHEDULE_CONFLICT", lambda: book(svc, users[2], another))
    check_error(
        "INVALID_APPOINTMENT_TRANSITION",
        lambda: svc.transition(users[0], appt.appointment_id, "complete"),
    )
    result = svc.transition(
        users[0], appt.appointment_id, "reject", "Choose another time"
    )
    assert (
        result.status == "REJECTED" and result.rejection_note == "Choose another time"
    )
    assert book(svc, users[3], first).status == "PENDING"
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) >= 4


def test_reschedule_revalidation_and_rollback(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    first = create_slot(svc, users[0], campus)
    second = create_slot(svc, users[0], campus, "FACE_TO_FACE", 3)
    appt = book(svc, users[2], first)
    data = AppointmentCreateRequest(
        availability_slot_id=second.slot_id, appointment_mode="FACE_TO_FACE"
    )
    check_error(
        "INVALID_APPOINTMENT_TRANSITION",
        lambda: svc.reschedule(users[2], appt.appointment_id, data),
    )
    svc.transition(users[0], appt.appointment_id, "confirm")
    campus.guidance_office_location = None
    db_session.flush()
    check_error(
        "GUIDANCE_OFFICE_REQUIRED",
        lambda: svc.reschedule(users[2], appt.appointment_id, data),
    )
    assert svc.repository.find_slot(first.slot_id).status == "RESERVED"
    assert svc.repository.find_slot(second.slot_id).status == "AVAILABLE"
    svc.accounts.set_guidance_office_location(
        users[0], campus.campus_id, "Replacement office"
    )
    result = svc.reschedule(users[2], appt.appointment_id, data)
    assert (
        result.status == "PENDING" and result.meeting_location == "Replacement office"
    )
    assert svc.repository.find_slot(first.slot_id).status == "AVAILABLE"
    assert svc.repository.find_slot(second.slot_id).status == "RESERVED"
    svc.transition(users[2], appt.appointment_id, "cancel")
    assert svc.repository.find_slot(second.slot_id).status == "AVAILABLE"


@pytest.mark.parametrize(
    "action,target",
    [("complete", "COMPLETED"), ("no-show", "NO_SHOW"), ("cancel", "CANCELLED")],
)
def test_outcomes(db_session, actors, action, target):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    appt = book(svc, users[2], slot)
    svc.transition(users[0], appt.appointment_id, "confirm")
    if action != "cancel":
        check_error(
            "SESSION_NOT_STARTED",
            lambda: svc.transition(users[0], appt.appointment_id, action),
        )
    row = svc.repository.find_slot(slot.slot_id)
    row.starts_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    row.ends_at = row.starts_at + timedelta(hours=1)
    db_session.flush()
    assert svc.transition(users[0], appt.appointment_id, action).status == target
    check_error(
        "INVALID_APPOINTMENT_TRANSITION",
        lambda: svc.transition(users[0], appt.appointment_id, "cancel"),
    )


def test_ownership_roles_status_and_lists(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    appt = book(svc, users[2], slot)
    for outsider in [users[1], users[3]]:
        check_error(
            "APPOINTMENT_NOT_FOUND", lambda: svc.detail(outsider, appt.appointment_id)
        )
        check_error(
            "APPOINTMENT_NOT_FOUND",
            lambda: svc.transition(outsider, appt.appointment_id, "cancel"),
        )
        assert svc.list_appointments(outsider)["items"] == []
    assert len(svc.list_appointments(users[0])["items"]) == 1
    for actor in [users[2], users[4]]:
        check_error("FORBIDDEN_ROLE", lambda: create_slot(svc, actor, campus))
        check_error(
            "FORBIDDEN_ROLE",
            lambda: svc.accounts.set_guidance_office_location(
                actor, campus.campus_id, "No"
            ),
        )
    check_error("FORBIDDEN_ROLE", lambda: svc.list_slots(users[4]))
    check_error(
        "FORBIDDEN_ROLE",
        lambda: svc.transition(users[2], appt.appointment_id, "confirm"),
    )
    for state in ["PENDING_VERIFICATION", "VERIFICATION_EXPIRED"]:
        users[2].account_status = state
        db_session.flush()
        check_error("ACCOUNT_NOT_ACTIVE", lambda: svc.list_slots(users[2]))


def test_linked_conversation_closes_and_mismatch_denied(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    appt = book(svc, users[2], slot)
    svc.transition(users[0], appt.appointment_id, "confirm")
    conv = Conversation(
        student_user_id=users[3].user_id,
        counselor_user_id=users[0].user_id,
        conversation_type="APPOINTMENT",
        status="OPEN",
    )
    db_session.add(conv)
    db_session.flush()
    row = db_session.get(Appointment, appt.appointment_id)
    row.conversation_id = conv.conversation_id
    db_session.flush()
    check_error(
        "CONVERSATION_MISMATCH",
        lambda: svc.transition(users[0], appt.appointment_id, "cancel"),
    )
    conv.student_user_id = users[2].user_id
    db_session.flush()
    svc.transition(users[0], appt.appointment_id, "cancel")
    assert conv.status == "CLOSED" and conv.closed_at is not None


def test_http_contract_csrf_and_no_store(db_client, db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    response = db_client.post(
        "/api/v1/auth/login",
        json={"identifier": "APPT-2", "password": "synthetic-test-pass"},
    )
    token = response.json()["csrf_token"]
    payload = {"availability_slot_id": slot.slot_id, "appointment_mode": "ONLINE"}
    assert db_client.post("/api/v1/appointments", json=payload).status_code == 403
    response = db_client.post(
        "/api/v1/appointments", json=payload, headers={"X-CSRF-Token": token}
    )
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["starts_at"].endswith("Z")
    result = db_client.get("/api/v1/appointments?page=1&page_size=1")
    assert result.status_code == 200 and result.json()["total"] == 1
    assert db_client.get("/api/v1/availability-slots?page_size=101").status_code == 422
    assert (
        db_client.post(
            "/api/v1/availability-slots",
            json={
                "campus_id": campus.campus_id,
                "delivery_mode": "ONLINE",
                "starts_at": "2099-01-01T09:00:00",
                "ends_at": "2099-01-01T10:00:00",
                "slot_duration_minutes": 60,
            },
            headers={"X-CSRF-Token": token},
        ).status_code
        == 422
    )


def test_failed_transaction_leaves_slot_available(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    nested = db_session.begin_nested()
    appt = book(svc, users[2], slot)
    nested.rollback()
    db_session.expire_all()
    assert svc.repository.find_slot(slot.slot_id).status == "AVAILABLE"
    assert db_session.get(Appointment, appt.appointment_id) is None


@pytest.mark.parametrize("same_student", [False, True])
def test_concurrent_reservations(mysql_test_engine, same_student):
    # Committed synthetic fixtures only in the disposable schema; real separate connections.
    suffix = uuid4().hex
    with Session(mysql_test_engine, expire_on_commit=False) as db:
        campus = Campus(campus_name="Concurrent " + suffix)
        users = [
            User(
                email=f"race-{i}-{suffix}@example.edu",
                password_hash="unused",
                first_name="Synthetic",
                last_name="Race",
                role_code=role,
                account_status="ACTIVE",
            )
            for i, role in enumerate(["COUNSELOR", "COUNSELOR", "STUDENT", "STUDENT"])
        ]
        db.add_all([campus, *users])
        db.flush()
        svc = AppointmentsService(db)
        slot1 = create_slot(svc, users[0], campus, "ONLINE")
        slot2 = create_slot(svc, users[1], campus, "ONLINE") if same_student else slot1
        user_ids = [users[2].user_id, users[2 if same_student else 3].user_id]
        slot_ids = [slot1.slot_id, slot2.slot_id]
        db.commit()
    barrier = Barrier(2)

    def attempt(i):
        with Session(mysql_test_engine, expire_on_commit=False) as db:
            actor = db.get(User, user_ids[i])
            barrier.wait(timeout=10)
            try:
                AppointmentsService(db).book(
                    actor,
                    AppointmentCreateRequest(
                        availability_slot_id=slot_ids[i], appointment_mode="ONLINE"
                    ),
                )
                db.commit()
                return "PENDING"
            except AppError as exc:
                db.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [0, 1]))
    assert sorted(results) == sorted(
        ["PENDING", "SCHEDULE_CONFLICT" if same_student else "SLOT_UNAVAILABLE"]
    )


@pytest.mark.parametrize(
    "action", ["confirm", "reject", "cancel", "complete", "no-show"]
)
@pytest.mark.parametrize(
    "status", ["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "REJECTED", "NO_SHOW"]
)
def test_transition_matrix(db_session, actors, action, status):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    response = book(svc, users[2], slot)
    appointment = db_session.get(Appointment, response.appointment_id)
    appointment.status = status
    slot_row = svc.repository.find_slot(slot.slot_id)
    if action in ("complete", "no-show"):
        slot_row.starts_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(hours=1)
        slot_row.ends_at = slot_row.starts_at + timedelta(hours=1)
    db_session.flush()
    allowed = {
        "confirm": ["PENDING"],
        "reject": ["PENDING"],
        "cancel": ["PENDING", "CONFIRMED"],
        "complete": ["CONFIRMED"],
        "no-show": ["CONFIRMED"],
    }
    if status not in allowed[action]:
        check_error(
            "INVALID_APPOINTMENT_TRANSITION",
            lambda: svc.transition(users[0], appointment.appointment_id, action),
        )
    else:
        result = svc.transition(users[0], appointment.appointment_id, action)
        assert (
            result.status
            == {
                "confirm": "CONFIRMED",
                "reject": "REJECTED",
                "cancel": "CANCELLED",
                "complete": "COMPLETED",
                "no-show": "NO_SHOW",
            }[action]
        )


def test_counselor_can_cancel_when_student_enrollment_expires(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    slot = create_slot(svc, users[0], campus)
    appt = book(svc, users[2], slot)
    users[2].account_status = "VERIFICATION_EXPIRED"
    db_session.flush()
    assert svc.transition(users[0], appt.appointment_id, "cancel").status == "CANCELLED"


def test_simultaneous_confirm_reject(mysql_test_engine):
    suffix = uuid4().hex
    with Session(mysql_test_engine, expire_on_commit=False) as db:
        campus = Campus(campus_name="Decision " + suffix)
        counselor = User(
            email=f"decision-c-{suffix}@example.edu",
            password_hash="unused",
            first_name="C",
            last_name="Test",
            role_code="COUNSELOR",
            account_status="ACTIVE",
        )
        student = User(
            email=f"decision-s-{suffix}@example.edu",
            password_hash="unused",
            first_name="S",
            last_name="Test",
            role_code="STUDENT",
            account_status="ACTIVE",
        )
        db.add_all([campus, counselor, student])
        db.flush()
        svc = AppointmentsService(db)
        slot = create_slot(svc, counselor, campus, "ONLINE")
        appt = book(svc, student, slot)
        ids = counselor.user_id, appt.appointment_id, slot.slot_id
        db.commit()
    barrier = Barrier(2)

    def decide(action):
        with Session(mysql_test_engine, expire_on_commit=False) as db:
            actor = db.get(User, ids[0])
            barrier.wait(timeout=10)
            try:
                result = AppointmentsService(db).transition(actor, ids[1], action)
                db.commit()
                return result.status
            except AppError as exc:
                db.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ["confirm", "reject"]))
    assert results.count("INVALID_APPOINTMENT_TRANSITION") == 1
    with Session(mysql_test_engine) as db:
        appt = db.get(Appointment, ids[1])
        assert appt.status in ("CONFIRMED", "REJECTED")
        assert db.get(AvailabilitySlot, ids[2]).status == (
            "RESERVED" if appt.status == "CONFIRMED" else "AVAILABLE"
        )
