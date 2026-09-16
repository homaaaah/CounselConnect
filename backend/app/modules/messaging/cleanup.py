"""Reminder, safety-timeout, and message-retention maintenance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Event

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_engine
from app.modules.appointments.repository import AppointmentsRepository
from app.modules.messaging.realtime import registry
from app.modules.messaging.service import MessagingService

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _enqueue(channel: str, event: dict) -> bool:
    if not registry.has_subscribers(channel):
        return False
    future = registry.publish_from_thread(channel, event)
    if future is None:
        return False
    try:
        return future.result(timeout=5) > 0
    except Exception:
        return False


def run_maintenance_once(now=None) -> None:
    moment = now or utcnow()
    settings = get_settings()
    post_commit_events: list[tuple[str, dict]] = []
    with Session(get_engine(), expire_on_commit=False) as session:
        appointments = AppointmentsRepository(session)
        messaging = MessagingService(session)

        for candidate, slot in appointments.reminder_candidates(moment):
            appointment = appointments.lock_appointment(candidate.appointment_id)
            current_slot = appointments.find_slot(appointment.availability_slot_id, lock=True)
            if (
                appointment.status != "CONFIRMED"
                or appointment.appointment_mode != "ONLINE"
                or not (moment < current_slot.starts_at <= moment + timedelta(minutes=30))
            ):
                continue
            base_event = {
                "event": "appointment_reminder",
                "appointment_id": appointment.appointment_id,
                "starts_at": current_slot.starts_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                "message": "Your scheduled CounselConnect session begins soon. Open the app to check the time.",
            }
            if appointment.student_reminder_dispatched_at is None and _enqueue(
                f"user:{appointment.student_user_id}", base_event
            ):
                appointment.student_reminder_dispatched_at = moment
            if appointment.counselor_reminder_dispatched_at is None and _enqueue(
                f"user:{appointment.counselor_user_id}", base_event
            ):
                appointment.counselor_reminder_dispatched_at = moment

        timeout_cutoff = moment - timedelta(minutes=settings.chat_grace_minutes)
        for candidate, _slot in appointments.timeout_candidates(timeout_cutoff):
            appointment = appointments.lock_appointment(candidate.appointment_id)
            conversation = messaging.for_appointment(appointment)
            if conversation is None or conversation.status != "OPEN":
                continue
            messaging.close_for_appointment(
                appointment, "TIMEOUT", closed_at=moment
            )
            event = {"event": "session_closed", "appointment_id": appointment.appointment_id, "reason": "TIMEOUT"}
            post_commit_events.extend([
                (f"conversation:{conversation.conversation_id}", event),
                (f"user:{appointment.student_user_id}", event),
                (f"user:{appointment.counselor_user_id}", event),
            ])

        purge_cutoff = moment - timedelta(days=settings.chat_retention_days)
        for conversation in messaging.repository.list_closed_conversations_purge_due(purge_cutoff):
            messaging.repository.delete_messages(conversation.conversation_id)
            conversation.messages_purged_at = moment

        session.commit()

    for channel, event in post_commit_events:
        registry.publish_from_thread(channel, event)


def maintenance_loop(stop: Event) -> None:
    interval = get_settings().chat_maintenance_interval_seconds
    while not stop.is_set():
        try:
            run_maintenance_once()
        except Exception:
            logger.error("messaging_maintenance_worker_failed; retry scheduled")
        if stop.wait(interval):
            break
