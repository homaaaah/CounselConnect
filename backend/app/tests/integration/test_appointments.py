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
    AppointmentRescheduleRequest,
    WeeklyScheduleCreateRequest,
)
from app.modules.appointments.service import AppointmentsService
from app.modules.audit.models import AuditEvent
from app.modules.messaging.models import Conversation
from app.modules.messaging.schemas import MessageCreateRequest
from app.modules.messaging.service import MessagingService


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


def test_scheduled_chat_is_lazy_joined_ordered_and_counselor_only_after_close(
    db_session, actors
):
    users, campus = actors
    now = datetime.now(timezone.utc).replace(tzinfo=None, second=0, microsecond=0)
    slot = AvailabilitySlot(
        counselor_user_id=users[0].user_id,
        campus_id=campus.campus_id,
        delivery_mode="BOTH",
        starts_at=now - timedelta(minutes=5),
        ends_at=now + timedelta(minutes=55),
        status="RESERVED",
    )
    db_session.add(slot)
    db_session.flush()
    appointment = Appointment(
        student_user_id=users[2].user_id,
        counselor_user_id=users[0].user_id,
        availability_slot_id=slot.slot_id,
        appointment_mode="ONLINE",
        status="CONFIRMED",
    )
    db_session.add(appointment)
    db_session.flush()

    messaging = MessagingService(db_session)
    conversation = messaging.join_appointment(users[2], appointment.appointment_id)
    assert appointment.conversation_id == conversation.conversation_id
    assert conversation.student_joined_at is not None
    assert conversation.counselor_joined_at is None
    check_error(
        "CONVERSATION_NOT_FOUND",
        lambda: messaging.history(users[0], conversation.conversation_id),
    )

    assert (
        messaging.join_appointment(users[0], appointment.appointment_id).conversation_id
        == conversation.conversation_id
    )
    first = messaging.send_message(
        users[2],
        conversation.conversation_id,
        MessageCreateRequest(body="Hello", client_message_id="student-1"),
    )
    retry = messaging.send_message(
        users[2],
        conversation.conversation_id,
        MessageCreateRequest(body="Hello", client_message_id="student-1"),
    )
    second = messaging.send_message(
        users[0],
        conversation.conversation_id,
        MessageCreateRequest(body="Welcome", client_message_id="counselor-1"),
    )
    assert retry.message_id == first.message_id
    assert [first.sequence_number, second.sequence_number] == [1, 2]

    AppointmentsService(db_session).transition(
        users[0], appointment.appointment_id, "complete"
    )
    assert conversation.status == "CLOSED"
    assert conversation.closure_reason == "COUNSELOR_OUTCOME"
    check_error(
        "CONVERSATION_NOT_FOUND",
        lambda: messaging.history(users[2], conversation.conversation_id),
    )
    assert [item.sequence_number for item in messaging.history(
        users[0], conversation.conversation_id
    )["items"]] == [1, 2]


def test_confirmation_does_not_create_chat_and_prestart_mode_change_keeps_confirmation(
    db_session, actors
):
    users, campus = actors
    appointments = AppointmentsService(db_session)
    slot = create_slot(appointments, users[0], campus, "BOTH")
    booked = book(appointments, users[2], slot, "ONLINE")
    confirmed = appointments.transition(users[0], booked.appointment_id, "confirm")
    assert confirmed.conversation_id is None
    assert db_session.query(Conversation).filter_by(appointment_id=booked.appointment_id).count() == 0

    changed = appointments.change_mode(
        users[0],
        booked.appointment_id,
        type("ModeChange", (), {"appointment_mode": "FACE_TO_FACE"})(),
    )
    assert changed.status == "CONFIRMED"
    assert changed.appointment_mode == "FACE_TO_FACE"
    assert changed.meeting_location == campus.guidance_office_location


def test_student_cannot_cancel_or_reschedule_inside_24_hour_cutoff(db_session, actors):
    users, campus = actors
    now = datetime.now(timezone.utc).replace(tzinfo=None, second=0, microsecond=0)
    slot = AvailabilitySlot(
        counselor_user_id=users[0].user_id,
        campus_id=campus.campus_id,
        delivery_mode="ONLINE",
        starts_at=now + timedelta(hours=23),
        ends_at=now + timedelta(hours=24),
        status="RESERVED",
    )
    db_session.add(slot)
    db_session.flush()
    appointment = Appointment(
        student_user_id=users[2].user_id,
        counselor_user_id=users[0].user_id,
        availability_slot_id=slot.slot_id,
        appointment_mode="ONLINE",
        status="CONFIRMED",
    )
    db_session.add(appointment)
    db_session.flush()
    appointments = AppointmentsService(db_session)
    check_error(
        "APPOINTMENT_CHANGE_CUTOFF",
        lambda: appointments.transition(users[2], appointment.appointment_id, "cancel"),
    )
    replacement = create_slot(appointments, users[0], campus, "ONLINE", offset=3)
    check_error(
        "APPOINTMENT_CHANGE_CUTOFF",
        lambda: appointments.reschedule(
            users[2],
            appointment.appointment_id,
            AppointmentRescheduleRequest(
                availability_slot_id=replacement.slot_id,
                appointment_mode="ONLINE",
            ),
        ),
    )


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


def test_calendar_counts_real_future_unreserved_times(db_session, actors, monkeypatch):
    from datetime import date
    from app.modules.appointments import service as module
    from app.modules.appointments.models import CounselorAvailabilityBlock

    users, campus = actors
    svc = AppointmentsService(db_session)
    # Friday, 1:30 PM Manila; use UTC persistence, independent of test host TZ.
    monkeypatch.setattr(module, "utcnow", lambda: datetime(2026, 9, 11, 5, 30))
    today = date(2026, 9, 11)
    assert svc.calendar(users[2], today, today)["days"][0]["available_times"] == []
    for hour, minute, owner, status in [
        (5, 0, 0, "AVAILABLE"), (5, 30, 0, "AVAILABLE"),
        (6, 0, 0, "RESERVED"), (6, 30, 0, "AVAILABLE"),
        (7, 0, 0, "AVAILABLE"), (7, 30, 0, "AVAILABLE"),
        (7, 0, 1, "AVAILABLE"),
    ]:
        start = datetime(2026, 9, 11, hour, minute)
        db_session.add(AvailabilitySlot(counselor_user_id=users[owner].user_id,
            campus_id=campus.campus_id, delivery_mode="ONLINE", status=status,
            starts_at=start, ends_at=start + timedelta(minutes=30)))
    db_session.add(CounselorAvailabilityBlock(counselor_user_id=users[0].user_id,
        starts_at=datetime(2026, 9, 11, 6, 30), ends_at=datetime(2026, 9, 11, 7),
        is_all_day=False))
    db_session.flush()
    result = svc.calendar(users[2], today - timedelta(days=1), today + timedelta(days=3))
    days = {day["calendar_date"]: day for day in result["days"]}
    assert days[today]["available_times"] == ["15:00", "15:30"]
    assert days[today - timedelta(days=1)]["is_past"] is True
    assert days[today - timedelta(days=1)]["available_times"] == []
    assert days[today + timedelta(days=3)]["available_times"] == []
    assert svc.calendar(users[1], today, today)["days"][0]["available_times"] == ["15:00"]
    # A whole-day block applies only to its owner; another Counselor stays open.
    svc.repository.add_blocked_date(users[0].user_id, today)
    db_session.flush()
    student_day = svc.calendar(users[2], today, today)["days"][0]
    assert student_day["available_times"] == ["15:00"]
    assert student_day["is_blocked"] is False
    assert svc.calendar(users[0], today, today)["days"][0]["available_times"] == []


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


def test_weekly_schedule_replacement_is_atomic_and_keeps_existing_slots(db_session, actors):
    users, campus = actors
    svc = AppointmentsService(db_session)
    initial = WeeklyScheduleCreateRequest(
        campus_id=campus.campus_id, day_of_week=1, start_time="08:00",
        end_time="10:00", slot_duration_minutes=30, delivery_mode="ONLINE",
    )
    original = svc.create_weekly_schedule(users[0], initial)
    start = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)
    existing_slot = AvailabilitySlot(
        counselor_user_id=users[0].user_id, campus_id=campus.campus_id,
        delivery_mode="ONLINE", starts_at=start, ends_at=start + timedelta(minutes=30),
        status="AVAILABLE", weekly_schedule_id=original.weekly_schedule_id,
    )
    db_session.add(existing_slot)
    db_session.flush()
    replacement = svc.replace_weekly_schedule(
        users[0], original.weekly_schedule_id,
        WeeklyScheduleCreateRequest(
            campus_id=campus.campus_id, day_of_week=1, start_time="08:00",
            end_time="11:00", slot_duration_minutes=30, delivery_mode="ONLINE",
        ),
    )
    db_session.refresh(original)
    db_session.refresh(existing_slot)
    assert original.is_active is False
    assert replacement.is_active is True
    assert replacement.weekly_schedule_id != original.weekly_schedule_id
    assert existing_slot.weekly_schedule_id == original.weekly_schedule_id
    svc.create_weekly_schedule(
        users[0],
        WeeklyScheduleCreateRequest(
            campus_id=campus.campus_id, day_of_week=1, start_time="12:00",
            end_time="14:00", slot_duration_minutes=30, delivery_mode="ONLINE",
        ),
    )
    check_error(
        "SCHEDULE_CONFLICT",
        lambda: svc.replace_weekly_schedule(
            users[0], replacement.weekly_schedule_id,
            WeeklyScheduleCreateRequest(
                campus_id=campus.campus_id, day_of_week=1, start_time="09:00",
                end_time="13:00", slot_duration_minutes=30, delivery_mode="ONLINE",
            ),
        ),
    )
    db_session.refresh(replacement)
    assert replacement.is_active is True


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
    conv.appointment_id = row.appointment_id
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
    # Separate-connection race fixtures commit into the session-scoped schema.
    # Retire every synthetic slot so later live UI tests cannot book one.
    with Session(mysql_test_engine) as db:
        for slot_id in set(slot_ids):
            db.get(AvailabilitySlot, slot_id).status = "RESERVED"
        db.commit()


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
        # Retire the committed race fixture after asserting its real outcome.
        db.get(AvailabilitySlot, ids[2]).status = "RESERVED"
        db.commit()


@pytest.mark.parametrize("role_index", [0, 2])
def test_slot_blocks_are_filtered_before_pagination(db_session, actors, role_index):
    from app.modules.appointments.models import CounselorAvailabilityBlock

    users, campus = actors
    svc = AppointmentsService(db_session)
    start = datetime.now(timezone.utc).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=3)
    slots = [AvailabilitySlot(
        counselor_user_id=users[0].user_id, campus_id=campus.campus_id,
        delivery_mode="ONLINE", status="AVAILABLE",
        starts_at=start + timedelta(minutes=15 * i),
        ends_at=start + timedelta(minutes=15 * (i + 1)),
    ) for i in range(50)]
    db_session.add_all(slots)
    # Two overlapping blocks must not duplicate results; their union hides 5 slots.
    db_session.add_all([CounselorAvailabilityBlock(
        counselor_user_id=users[0].user_id, starts_at=start,
        ends_at=start + timedelta(minutes=minutes), is_all_day=False,
    ) for minutes in (45, 75)])
    db_session.flush()
    # Campus scoping keeps exact totals independent of the concurrency
    # tests, which commit on separate connections into the shared schema.
    pages = [svc.list_slots(users[role_index], campus_id=campus.campus_id, page=n) for n in range(1, 5)]
    assert [p["total"] for p in pages] == [45] * 4
    assert [len(p["items"]) for p in pages] == [20, 20, 5, 0]
    assert [item.slot_id for p in pages for item in p["items"]] == [s.slot_id for s in slots[5:]]


def test_slot_date_blocks_are_owner_scoped_and_use_manila_date(db_session, actors):
    from app.modules.appointments.models import CounselorBlockedDate

    users, campus = actors
    svc = AppointmentsService(db_session)
    # 16:00 UTC is midnight on the following Philippine calendar date.
    start = datetime.now(timezone.utc).replace(tzinfo=None, hour=16, minute=0, second=0, microsecond=0) + timedelta(days=3)
    slots = [AvailabilitySlot(
        counselor_user_id=owner.user_id, campus_id=campus.campus_id,
        delivery_mode="ONLINE", status="AVAILABLE",
        starts_at=start + timedelta(minutes=offset),
        ends_at=start + timedelta(minutes=offset + 15),
    ) for owner, offset in [(users[0], -15), (users[0], 0), (users[1], 0)]]
    db_session.add_all(slots)
    db_session.add(CounselorBlockedDate(
        counselor_user_id=users[0].user_id,
        blocked_date=(start + timedelta(hours=8)).date(),
    ))
    db_session.flush()
    # Campus scoping: see test_slot_blocks_are_filtered_before_pagination.
    result = svc.list_slots(users[2], campus_id=campus.campus_id, page_size=1)
    assert result["total"] == 2
    assert [s.slot_id for s in result["items"]] == [slots[0].slot_id]
    assert [s.slot_id for s in svc.list_slots(users[2], campus_id=campus.campus_id, page=2, page_size=1)["items"]] == [slots[2].slot_id]
    # Counselor scope remains private even when another counselor is unblocked.
    assert [s.slot_id for s in svc.list_slots(users[0])["items"]] == [slots[0].slot_id]
