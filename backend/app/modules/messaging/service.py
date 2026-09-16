"""messaging service: authorization + business rules.

Core rules (docs/REAL_TIME_MESSAGING.md, ARCHITECTURE.md):
- One Student <-> one Counselor per conversation; GENERAL, APPOINTMENT, and
  SOS types with distinct entry authorization.
- Only participants recorded on an OPEN conversation may exchange messages.
- Message bodies are purged 30 days after closure; only permitted
  conversation metadata remains.
- Appointments/SOS modules request conversations through THIS service
  (service contract), never by creating records directly.

# Real-time delivery uses native WebSockets; REST remains the durable authority.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.config import get_settings
from app.core.exceptions import AppError
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.repository import MessagingRepository


class MessagingService(BaseService[Conversation]):
    """Real-time messaging business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(MessagingRepository(session))

    def for_appointment(self, appointment):
        conversation = self.repository.conversation_by_appointment(
            appointment.appointment_id
        )
        if appointment.conversation_id is None:
            if conversation is not None:
                raise AppError("CONVERSATION_MISMATCH", "The appointment session link is invalid.")
            return None
        if (
            conversation is None
            or conversation.conversation_id != appointment.conversation_id
            or conversation.conversation_type != "APPOINTMENT"
            or conversation.student_user_id != appointment.student_user_id
            or conversation.counselor_user_id != appointment.counselor_user_id
        ):
            raise AppError("CONVERSATION_MISMATCH", "The appointment session link is invalid.")
        return conversation

    def has_activity(self, appointment):
        conversation = self.for_appointment(appointment)
        return bool(
            conversation
            and (
                conversation.student_joined_at is not None
                or conversation.counselor_joined_at is not None
                or conversation.last_sequence_number > 0
                or self.repository.message_count(conversation.conversation_id) > 0
            )
        )

    def delete_unused_for_appointment(self, appointment):
        conversation = self.for_appointment(appointment)
        if conversation is None:
            return
        conversation = self.repository.lock_conversation(conversation.conversation_id)
        if (
            conversation.student_joined_at is not None
            or conversation.counselor_joined_at is not None
            or conversation.last_sequence_number > 0
            or self.repository.message_count(conversation.conversation_id) > 0
        ):
            raise AppError(
                "SESSION_ALREADY_ACTIVE",
                "The appointment session already has participant activity.",
            )
        appointment.conversation_id = None
        conversation.appointment_id = None
        self.repository.session.flush()
        self.repository.delete(conversation)
        self.repository.session.flush()

    def close_for_appointment(
        self, appointment, reason="COUNSELOR_OUTCOME", *, closed_at=None
    ):
        """Internal call after the appointment service locks and authorizes the outcome."""
        from datetime import datetime, timezone
        conversation = self.repository.lock_conversation(appointment.conversation_id)
        if (conversation is None or conversation.conversation_type != "APPOINTMENT"
            or appointment.appointment_mode != "ONLINE"
            or conversation.student_user_id != appointment.student_user_id
            or conversation.counselor_user_id != appointment.counselor_user_id):
            raise AppError("CONVERSATION_MISMATCH", "The appointment session link is invalid.")
        if conversation.status == "OPEN":
            conversation.status = "CLOSED"
            conversation.closed_at = closed_at or datetime.now(timezone.utc).replace(tzinfo=None)
            conversation.closure_reason = reason

    @staticmethod
    def _utcnow():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _authorize_actor(actor):
        if actor.role_code not in ("STUDENT", "COUNSELOR"):
            raise AppError("FORBIDDEN_ROLE", "You do not have access to appointment chat.", status_code=403)
        if actor.account_status != "ACTIVE":
            raise AppError("ACCOUNT_NOT_ACTIVE", "An active verified account is required.", status_code=403)

    def join_appointment(self, actor, appointment_id):
        from app.modules.appointments.service import AppointmentsService

        self._authorize_actor(actor)
        appointments = AppointmentsService(self.repository.session)
        appointment = appointments.lock_session_appointment(actor, appointment_id)
        slot = appointments.repository.find_slot(appointment.availability_slot_id, lock=True)
        now = self._utcnow()
        deadline = slot.ends_at + timedelta(minutes=get_settings().chat_grace_minutes)
        if appointment.status != "CONFIRMED" or appointment.appointment_mode != "ONLINE":
            raise AppError("SESSION_UNAVAILABLE", "This appointment does not have an available online session.", status_code=403)
        if now < slot.starts_at:
            raise AppError("SESSION_NOT_STARTED", "Messaging opens at the scheduled start.")
        if now >= deadline:
            raise AppError("SESSION_CLOSED", "The scheduled messaging window has ended.")

        conversation = self.for_appointment(appointment)
        if conversation is None:
            conversation = Conversation(
                student_user_id=appointment.student_user_id,
                counselor_user_id=appointment.counselor_user_id,
                appointment_id=appointment.appointment_id,
                conversation_type="APPOINTMENT",
                status="OPEN",
                started_at=now,
                last_sequence_number=0,
            )
            self.repository.add(conversation)
            self.repository.session.flush()
            appointment.conversation_id = conversation.conversation_id
        elif conversation.status != "OPEN":
            raise AppError("SESSION_CLOSED", "This appointment conversation is closed.")
        if actor.role_code == "STUDENT" and conversation.student_joined_at is None:
            conversation.student_joined_at = now
        if actor.role_code == "COUNSELOR" and conversation.counselor_joined_at is None:
            conversation.counselor_joined_at = now
        self.repository.session.flush()
        return conversation

    def _authorized_conversation(self, actor, conversation_id, *, lock=False):
        from app.modules.appointments.service import AppointmentsService

        self._authorize_actor(actor)
        initial = self.repository.get(conversation_id)
        if initial is None or initial.conversation_type != "APPOINTMENT" or initial.appointment_id is None:
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", status_code=404)
        appointments = AppointmentsService(self.repository.session)
        appointment = (
            appointments.lock_session_appointment(actor, initial.appointment_id)
            if lock
            else appointments.session_appointment(actor, initial.appointment_id)
        )
        conversation = self.repository.lock_conversation(conversation_id) if lock else initial
        if (
            conversation is None
            or appointment.conversation_id != conversation.conversation_id
            or conversation.appointment_id != appointment.appointment_id
            or conversation.student_user_id != appointment.student_user_id
            or conversation.counselor_user_id != appointment.counselor_user_id
        ):
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", status_code=404)
        return appointment, conversation

    def _history_allowed(self, actor, appointment, conversation):
        if conversation.messages_purged_at is not None:
            return False
        if conversation.status == "CLOSED":
            if actor.role_code != "COUNSELOR":
                return False
            cutoff = conversation.closed_at + timedelta(days=get_settings().chat_retention_days)
            return self._utcnow() < cutoff
        from app.modules.appointments.service import AppointmentsService

        slot = AppointmentsService(self.repository.session).repository.find_slot(
            appointment.availability_slot_id
        )
        within_window = (
            appointment.status == "CONFIRMED"
            and appointment.appointment_mode == "ONLINE"
            and slot.starts_at <= self._utcnow()
            < slot.ends_at + timedelta(minutes=get_settings().chat_grace_minutes)
        )
        return within_window and bool(
            conversation.student_joined_at
            if actor.role_code == "STUDENT"
            else conversation.counselor_joined_at
        )

    def conversation_detail(self, actor, conversation_id):
        appointment, conversation = self._authorized_conversation(actor, conversation_id)
        if not self._history_allowed(actor, appointment, conversation):
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", status_code=404)
        return conversation

    def history(self, actor, conversation_id, *, before_sequence=None, after_sequence=None, limit=50):
        if before_sequence is not None and after_sequence is not None:
            raise AppError("INVALID_MESSAGE_CURSOR", "Choose either before_sequence or after_sequence.", status_code=422)
        appointment, conversation = self._authorized_conversation(actor, conversation_id)
        if not self._history_allowed(actor, appointment, conversation):
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", status_code=404)
        items, has_more = self.repository.message_history(
            conversation_id,
            before_sequence=before_sequence,
            after_sequence=after_sequence,
            limit=limit,
        )
        return {
            "items": items,
            "next_before_sequence": items[0].sequence_number if items and has_more and after_sequence is None else None,
            "next_after_sequence": items[-1].sequence_number if items else after_sequence,
            "has_more": has_more,
            "sequence_watermark": conversation.last_sequence_number,
        }

    def send_message(self, actor, conversation_id, data):
        appointment, conversation = self._authorized_conversation(actor, conversation_id, lock=True)
        if not self._history_allowed(actor, appointment, conversation):
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", status_code=404)
        existing = self.repository.find_message_by_client_id(conversation_id, data.client_message_id)
        if existing is not None:
            if existing.sender_user_id != actor.user_id or existing.body != data.body:
                raise AppError("CLIENT_MESSAGE_ID_CONFLICT", "This client message ID was already used for different content.")
            return existing
        if conversation.status != "OPEN":
            raise AppError("SESSION_CLOSED", "This appointment conversation is closed.")
        from app.modules.appointments.service import AppointmentsService

        slot = AppointmentsService(self.repository.session).repository.find_slot(appointment.availability_slot_id)
        now = self._utcnow()
        deadline = slot.ends_at + timedelta(minutes=get_settings().chat_grace_minutes)
        if now < slot.starts_at or now >= deadline or appointment.status != "CONFIRMED" or appointment.appointment_mode != "ONLINE":
            raise AppError("SESSION_CLOSED", "Messages are not available for this appointment.")
        joined = (
            conversation.student_joined_at
            if actor.role_code == "STUDENT"
            else conversation.counselor_joined_at
        )
        if joined is None:
            raise AppError("SESSION_JOIN_REQUIRED", "Join the appointment session before sending messages.")
        if not data.body.strip():
            raise AppError("MESSAGE_EMPTY", "Enter a message before sending.", status_code=422)
        if len(data.body) > get_settings().chat_max_message_characters:
            raise AppError("MESSAGE_TOO_LONG", "The message is too long.", status_code=422)
        conversation.last_sequence_number += 1
        message = Message(
            conversation_id=conversation.conversation_id,
            sender_user_id=actor.user_id,
            client_message_id=data.client_message_id,
            sequence_number=conversation.last_sequence_number,
            body=data.body,
            sent_at=now,
        )
        self.repository.session.add(message)
        self.repository.session.flush()
        return message


def get_messaging_service(session: Session = Depends(get_session)) -> MessagingService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return MessagingService(session)
