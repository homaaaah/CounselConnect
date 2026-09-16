"""MySQL checks for scheduled-chat timeout and retention maintenance."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import Campus, User
from app.modules.appointments.models import Appointment, AvailabilitySlot
from app.modules.messaging.cleanup import run_maintenance_once
from app.modules.messaging.models import Conversation, Message


def test_timeout_preserves_outcome_and_retention_purges_bodies(
    mysql_test_engine, monkeypatch
):
    monkeypatch.setattr(
        "app.modules.messaging.cleanup.get_engine", lambda: mysql_test_engine
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    suffix = uuid4().hex
    with Session(mysql_test_engine, expire_on_commit=False) as session:
        campus = Campus(campus_name="Chat maintenance " + suffix)
        student = User(
            email=f"chat-student-{suffix}@example.edu",
            password_hash="unused",
            role_code="STUDENT",
            account_status="ACTIVE",
            first_name="Ana",
            last_name="Chat",
        )
        counselor = User(
            email=f"chat-counselor-{suffix}@example.edu",
            password_hash="unused",
            role_code="COUNSELOR",
            account_status="ACTIVE",
            first_name="Cora",
            last_name="Chat",
        )
        session.add_all([campus, student, counselor])
        session.flush()
        slot = AvailabilitySlot(
            counselor_user_id=counselor.user_id,
            campus_id=campus.campus_id,
            delivery_mode="ONLINE",
            starts_at=now - timedelta(hours=1),
            ends_at=now - timedelta(minutes=16),
            status="RESERVED",
        )
        session.add(slot)
        session.flush()
        appointment = Appointment(
            student_user_id=student.user_id,
            counselor_user_id=counselor.user_id,
            availability_slot_id=slot.slot_id,
            appointment_mode="ONLINE",
            status="CONFIRMED",
        )
        session.add(appointment)
        session.flush()
        active = Conversation(
            student_user_id=student.user_id,
            counselor_user_id=counselor.user_id,
            appointment_id=appointment.appointment_id,
            conversation_type="APPOINTMENT",
            status="OPEN",
            last_sequence_number=0,
        )
        expired = Conversation(
            student_user_id=student.user_id,
            counselor_user_id=counselor.user_id,
            conversation_type="GENERAL",
            status="CLOSED",
            closed_at=now - timedelta(days=31),
            last_sequence_number=1,
        )
        session.add_all([active, expired])
        session.flush()
        appointment.conversation_id = active.conversation_id
        expired_message = Message(
            conversation_id=expired.conversation_id,
            sender_user_id=student.user_id,
            client_message_id="expired-1",
            sequence_number=1,
            body="retained body due for deletion",
            sent_at=now - timedelta(days=31),
        )
        session.add(expired_message)
        session.commit()
        appointment_id = appointment.appointment_id
        active_id = active.conversation_id
        expired_id = expired.conversation_id

    run_maintenance_once(now)

    with Session(mysql_test_engine) as session:
        appointment = session.get(Appointment, appointment_id)
        active = session.get(Conversation, active_id)
        expired = session.get(Conversation, expired_id)
        assert appointment.status == "CONFIRMED"
        assert active.status == "CLOSED"
        assert active.closure_reason == "TIMEOUT"
        assert active.closed_at == now
        assert expired.messages_purged_at == now
        assert session.scalar(
            select(Message).where(Message.conversation_id == expired_id)
        ) is None
