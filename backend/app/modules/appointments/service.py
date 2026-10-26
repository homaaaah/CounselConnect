"""Atomic scheduling workflow from Flowchart V1, page 4."""

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.config import get_settings
from app.database import get_session
from app.modules.accounts.service import AccountsService
from app.modules.audit.service import AuditService
from app.modules.bases import BaseService
from app.modules.appointments.models import (
    Appointment,
    AvailabilitySlot,
    CounselorAvailabilityBlock,
    CounselorWeeklySchedule,
    SessionDocument,
    SessionRecord,
)
from app.modules.appointments.repository import AppointmentsRepository
from app.modules.appointments.schemas import (
    AppointmentResponse,
    AppointmentSessionResponse,
    AvailabilitySlotResponse,
    SessionDocumentResponse,
    SessionRecordResponse,
    SessionRecordUpdateRequest,
    WeeklyScheduleCreateRequest,
)

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def manila_today():
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def db_time(value):
    return (
        value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    )


@dataclass(frozen=True)
class CallContext:
    """Authorized, ephemeral call window for one appointment participant."""

    appointment: Appointment
    actor_role: str
    peer_role: str
    starts_at: datetime
    ends_at: datetime
    safety_deadline_at: datetime
    server_time: datetime
    can_call: bool


class AppointmentsService(BaseService[Appointment]):
    def __init__(self, session: Session):
        super().__init__(AppointmentsRepository(session))
        self.accounts = AccountsService(session)
        self.audit = AuditService(session)

    def ensure_schedule_slots(self, start_date, end_date, counselor_id=None):
        """Materialize only the searched dates from active weekly schedules."""
        schedules = self.repository.active_weekly_schedules(counselor_id)
        changed = 0
        for offset in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=offset)
            for schedule in schedules:
                if day.isoweekday() != schedule.day_of_week:
                    continue
                local_start = datetime.combine(day, schedule.start_time, tzinfo=ZoneInfo("Asia/Manila"))
                local_end = datetime.combine(day, schedule.end_time, tzinfo=ZoneInfo("Asia/Manila"))
                duration = timedelta(minutes=schedule.slot_duration_minutes)
                while local_start < local_end:
                    start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
                    end = (local_start + duration).astimezone(timezone.utc).replace(tzinfo=None)
                    if not self.repository.overlapping_availability_blocks(
                        schedule.counselor_user_id, start, end
                    ):
                        existing = self.repository.find_slot_exact(
                            schedule.counselor_user_id,
                            schedule.campus_id,
                            start,
                            end,
                        )
                        if existing is None:
                            self.repository.session.add(AvailabilitySlot(
                                counselor_user_id=schedule.counselor_user_id,
                                campus_id=schedule.campus_id,
                                delivery_mode=schedule.delivery_mode,
                                starts_at=start,
                                ends_at=end,
                                status="AVAILABLE",
                                weekly_schedule_id=schedule.weekly_schedule_id,
                            ))
                            changed += 1
                        elif existing.status == "AVAILABLE" and (
                            existing.delivery_mode != schedule.delivery_mode
                            or existing.weekly_schedule_id != schedule.weekly_schedule_id
                        ):
                            # A slot can already exist because this recurring
                            # definition replaced an older mode, or because a
                            # matching manual slot was materialized earlier.
                            # Only unreserved future availability follows the
                            # active definition; reservations and appointments
                            # keep their original slot unchanged.
                            existing.delivery_mode = schedule.delivery_mode
                            existing.weekly_schedule_id = schedule.weekly_schedule_id
                            changed += 1
                    local_start += duration
        if changed:
            self.repository.session.flush()

    def booking_counselors(self, actor):
        self.authorize(actor, ("STUDENT",))
        return [
            {"counselor_user_id": user.user_id,
             "counselor_name": f"{user.first_name} {user.last_name}"}
            for user in self.repository.active_counselors()
        ]

    def calendar(self, actor, start_date: date, end_date: date, counselor_user_id=None):
        self.authorize(actor)
        if actor.role_code == "COUNSELOR":
            counselor_user_id = actor.user_id
        elif counselor_user_id is not None:
            counselor = self.accounts.scheduling_user(counselor_user_id)
            if counselor is None or counselor.role_code != "COUNSELOR" or counselor.account_status != "ACTIVE":
                raise AppError("COUNSELOR_NOT_FOUND", "The selected Counselor is unavailable.", status_code=404)
        if end_date < start_date or (end_date - start_date).days > 62:
            raise AppError("INVALID_CALENDAR_RANGE", "Choose a calendar range of 63 days or less.", status_code=422)
        now = utcnow()
        manila = ZoneInfo("Asia/Manila")
        today = now.replace(tzinfo=timezone.utc).astimezone(manila).date()
        self.ensure_schedule_slots(max(start_date, today), end_date, counselor_user_id)
        counselor_ids = [counselor_user_id] if counselor_user_id is not None else self.repository.active_counselor_ids()
        blocked_by_counselor = {
            counselor_id: self.repository.blocked_dates([counselor_id], start_date, end_date)
            for counselor_id in counselor_ids
        }
        blocked = set.intersection(*blocked_by_counselor.values()) if blocked_by_counselor else set()
        range_start = db_time(datetime.combine(start_date, datetime.min.time(), tzinfo=manila))
        range_end = db_time(datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=manila))
        times_by_date = {}
        slots_by_date = {}
        for slot in self.repository.calendar_slots(counselor_ids, now, range_start, range_end):
            local_start = slot.starts_at.replace(tzinfo=timezone.utc).astimezone(manila)
            if local_start.date() in blocked_by_counselor[slot.counselor_user_id]:
                continue
            start_time = local_start.strftime("%H:%M")
            times_by_date.setdefault(local_start.date(), set()).add(start_time)
            slot_end = getattr(slot, "ends_at", None)
            if slot_end is not None:
                local_end = slot_end.replace(tzinfo=timezone.utc).astimezone(manila)
                slots_by_date.setdefault(local_start.date(), set()).add(
                    (start_time, local_end.strftime("%H:%M"))
                )
        booked_by_date = {}
        if actor.role_code == "COUNSELOR":
            for slot, status in self.repository.booked_calendar_slots(
                actor.user_id, range_start, range_end
            ):
                local_start = slot.starts_at.replace(tzinfo=timezone.utc).astimezone(manila)
                local_end = slot.ends_at.replace(tzinfo=timezone.utc).astimezone(manila)
                booked_by_date.setdefault(local_start.date(), set()).add((
                    local_start.strftime("%H:%M"),
                    local_end.strftime("%H:%M"),
                    status,
                ))
        days = []
        for offset in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=offset)
            weekday = day.weekday() < 5
            is_past = day < today
            is_blocked = day in blocked
            # Weekly schedules support every ISO day (1 Monday through 7
            # Sunday). `is_weekday` remains descriptive for consumers, but
            # real weekend availability must remain bookable.
            if not is_blocked and not is_past:
                slots = sorted(slots_by_date.get(day, set()))
                times = sorted(times_by_date.get(day, set()))
            else:
                slots = []
                times = []
            days.append({"calendar_date": day, "is_weekday": weekday, "is_blocked": is_blocked, "is_past": is_past,
                "available_times": times,
                "available_slots": [{"start_time": start, "end_time": end} for start, end in slots],
                "booked_slots": [
                    {"start_time": start, "end_time": end, "status": status}
                    for start, end, status in sorted(booked_by_date.get(day, set()))
                ] if actor.role_code == "COUNSELOR" else []})
        return {"timezone": "Asia/Manila", "business_hours": "Availability set by counselors", "days": days}

    def block_date(self, actor, blocked_date, reason=None):
        self.authorize(actor, ("COUNSELOR",))
        if blocked_date < manila_today():
            raise AppError("INVALID_BLOCK_DATE", "A past date cannot be blocked.", status_code=422)
        if self.repository.blocked_date(actor.user_id, blocked_date):
            raise AppError("DATE_ALREADY_BLOCKED", "This date is already blocked.")
        block = self.repository.add_blocked_date(actor.user_id, blocked_date, reason)
        self.repository.session.flush()
        self.audit.record(actor.user_id, "counselor_date_blocked", "counselor_blocked_date", block.blocked_date_id)
        return block

    def unblock_date(self, actor, blocked_date):
        self.authorize(actor, ("COUNSELOR",))
        block = self.repository.remove_blocked_date(actor.user_id, blocked_date)
        if block is None:
            raise AppError("BLOCK_NOT_FOUND", "This date is not blocked.", status_code=404)
        self.audit.record(actor.user_id, "counselor_date_unblocked", "counselor_blocked_date", block.blocked_date_id)

    def authorize(self, actor, roles=("STUDENT", "COUNSELOR")):
        if actor.role_code not in roles:
            raise AppError(
                "FORBIDDEN_ROLE",
                "You do not have access to appointments.",
                status_code=403,
            )
        if actor.account_status != "ACTIVE":
            raise AppError(
                "ACCOUNT_NOT_ACTIVE",
                "An active verified account is required.",
                status_code=403,
            )

    def create_weekly_schedule(self, actor, data):
        """Store recurring university-local availability without changing appointments."""
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        matching = self.repository.matching_weekly_schedule(actor.user_id, data)
        if matching is not None and (getattr(matching, "is_deleted", False) or not matching.is_active):
            self._validate_weekly_schedule(actor, data, exclude_id=matching.weekly_schedule_id)
            matching.is_deleted = False
            matching.is_active = True
            self.repository.session.flush()
            self.audit.record(actor.user_id, "weekly_schedule_reactivated", "counselor_weekly_schedule", matching.weekly_schedule_id)
            return matching
        self._validate_weekly_schedule(actor, data)
        schedule = self.repository.create_weekly_schedule(
            counselor_user_id=actor.user_id,
            campus_id=data.campus_id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_duration_minutes=data.slot_duration_minutes,
            delivery_mode=data.delivery_mode,
        )
        self.repository.session.flush()
        self.audit.record(actor.user_id, "weekly_schedule_created", "counselor_weekly_schedule", schedule.weekly_schedule_id)
        return schedule

    def create_standard_weekday_schedules(self, actor, data):
        """Create or restore the Mon-Fri 08:00-16:00 schedules as one validated batch."""
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        prepared = []
        for day_of_week in range(1, 6):
            schedule_data = WeeklyScheduleCreateRequest(
                campus_id=data.campus_id,
                day_of_week=day_of_week,
                start_time=time(8, 0),
                end_time=time(16, 0),
                slot_duration_minutes=data.slot_duration_minutes,
                delivery_mode=data.delivery_mode,
            )
            matching = self.repository.matching_weekly_schedule(actor.user_id, schedule_data)
            already_active = matching is not None and matching.is_active and not getattr(matching, "is_deleted", False)
            self._validate_weekly_schedule(
                actor,
                schedule_data,
                exclude_id=matching.weekly_schedule_id if matching is not None else None,
            )
            prepared.append((schedule_data, matching, already_active))

        # Validate the full batch before any schedule changes; a conflict on
        # one weekday cannot leave the Counselor with a partial work week.
        schedules = []
        for schedule_data, matching, already_active in prepared:
            schedules.append(matching if already_active else self.create_weekly_schedule(actor, schedule_data))
        return schedules

    def replace_weekly_schedule(self, actor, weekly_schedule_id, data):
        """Atomically replace one active recurring definition without changing slots."""
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        previous = self.repository.lock_weekly_schedule(actor.user_id, weekly_schedule_id)
        if previous is None or getattr(previous, "is_deleted", False) or not previous.is_active:
            raise AppError("SCHEDULE_NOT_FOUND", "Weekly schedule not found.", status_code=404)
        if self._weekly_schedule_matches(previous, data):
            return previous
        self._validate_weekly_schedule(actor, data, exclude_id=weekly_schedule_id)
        replacement = self.repository.matching_weekly_schedule(
            actor.user_id, data, exclude_id=weekly_schedule_id
        )
        if replacement is None:
            replacement = self.repository.create_weekly_schedule(
                counselor_user_id=actor.user_id,
                campus_id=data.campus_id,
                day_of_week=data.day_of_week,
                start_time=data.start_time,
                end_time=data.end_time,
                slot_duration_minutes=data.slot_duration_minutes,
                delivery_mode=data.delivery_mode,
            )
        else:
            replacement.is_deleted = False
            replacement.is_active = True
        previous.is_active = False
        self.repository.session.flush()
        self.audit.record(actor.user_id, "weekly_schedule_replaced", "counselor_weekly_schedule", previous.weekly_schedule_id)
        return replacement

    def _validate_weekly_schedule(self, actor, data, *, exclude_id=None):
        campus = self._campus(data.campus_id)
        if data.delivery_mode != "ONLINE" and not (campus.guidance_office_location or "").strip():
            raise AppError("GUIDANCE_OFFICE_REQUIRED", "Configure the campus Guidance Office location first.")
        if self.repository.overlapping_weekly_schedule(
            actor.user_id, data.day_of_week, data.start_time, data.end_time,
            exclude_id=exclude_id,
        ):
            raise AppError("SCHEDULE_CONFLICT", "This weekly period overlaps an active schedule.")

    @staticmethod
    def _weekly_schedule_matches(schedule, data):
        return all(
            getattr(schedule, field) == getattr(data, field)
            for field in ("campus_id", "day_of_week", "start_time", "end_time", "slot_duration_minutes", "delivery_mode")
        )

    def list_weekly_schedules(self, actor):
        self.authorize(actor, ("COUNSELOR",))
        return self.repository.weekly_schedules(actor.user_id)

    def list_availability_blocks(self, actor):
        self.authorize(actor, ("COUNSELOR",))
        return self.repository.availability_blocks(actor.user_id)

    def deactivate_weekly_schedule(self, actor, weekly_schedule_id):
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        schedule = self.repository.deactivate_weekly_schedule(actor.user_id, weekly_schedule_id)
        if schedule is None or getattr(schedule, "is_deleted", False):
            raise AppError("SCHEDULE_NOT_FOUND", "Weekly schedule not found.", status_code=404)
        self.audit.record(actor.user_id, "weekly_schedule_deactivated", "counselor_weekly_schedule", schedule.weekly_schedule_id)

    def enable_weekly_schedule(self, actor, weekly_schedule_id):
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        schedule = self.repository.lock_weekly_schedule(actor.user_id, weekly_schedule_id)
        if schedule is None or schedule.is_deleted:
            raise AppError("SCHEDULE_NOT_FOUND", "Weekly schedule not found.", status_code=404)
        if schedule.is_active:
            return schedule
        self._validate_weekly_schedule(actor, schedule, exclude_id=weekly_schedule_id)
        schedule.is_active = True
        self.repository.session.flush()
        self.audit.record(actor.user_id, "weekly_schedule_enabled", "counselor_weekly_schedule", schedule.weekly_schedule_id)
        return schedule

    def delete_weekly_schedule(self, actor, weekly_schedule_id):
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        schedule = self.repository.delete_weekly_schedule(actor.user_id, weekly_schedule_id)
        if schedule is None:
            raise AppError("SCHEDULE_NOT_FOUND", "Weekly schedule not found.", status_code=404)
        self.audit.record(actor.user_id, "weekly_schedule_deleted", "counselor_weekly_schedule", schedule.weekly_schedule_id)

    def create_availability_block(self, actor, data):
        self.authorize(actor, ("COUNSELOR",))
        starts_at, ends_at = db_time(data.starts_at), db_time(data.ends_at)
        if starts_at <= utcnow():
            raise AppError("BLOCK_IN_PAST", "A block must start in the future.")
        # Serialize with booking/reschedule, which lock the same user row.
        self._participants(None, actor.user_id)
        if self.repository.overlapping_active_appointments(actor.user_id, starts_at, ends_at):
            raise AppError("BLOCK_CONFLICT", "Resolve overlapping pending or confirmed appointments first.")
        block = self.repository.create_availability_block(
            counselor_user_id=actor.user_id,
            starts_at=starts_at,
            ends_at=ends_at,
            is_all_day=data.is_all_day,
            reason=data.reason,
        )
        self.repository.session.flush()
        self.audit.record(actor.user_id, "availability_block_created", "counselor_availability_block", block.availability_block_id)
        return block

    def delete_availability_block(self, actor, availability_block_id):
        self.authorize(actor, ("COUNSELOR",))
        # Serialize with booking/block creation, which lock the same user row.
        self._participants(None, actor.user_id)
        block = self.repository.delete_availability_block(actor.user_id, availability_block_id)
        if block is None:
            raise AppError("BLOCK_NOT_FOUND", "Availability block not found.", status_code=404)
        self.audit.record(actor.user_id, "availability_block_deleted", "counselor_availability_block", availability_block_id)

    def _participants(self, student_id, *counselor_ids, require_active=True):
        # Global ascending user locks serialize cross-campus counselor and student conflicts.
        ids = set(counselor_ids)
        if student_id is not None:
            ids.add(student_id)
        for user_id in sorted(ids):
            user = self.accounts.scheduling_user(user_id, lock=True)
            expected = "STUDENT" if user_id == student_id else "COUNSELOR"
            if (
                user is None
                or user.role_code != expected
                or (require_active and user.account_status != "ACTIVE")
            ):
                raise AppError(
                    "PARTICIPANT_UNAVAILABLE",
                    "An appointment participant is unavailable.",
                )

    def _campus(self, campus_id):
        campus = self.accounts.scheduling_campus(campus_id, lock=True)
        if campus is None or not campus.is_active:
            raise AppError(
                "CAMPUS_NOT_FOUND",
                "Campus does not exist or is inactive.",
                status_code=404,
            )
        return campus

    def slot_response(self, slot):
        campus = self.accounts.scheduling_campus(slot.campus_id)
        counselor = self.accounts.scheduling_user(slot.counselor_user_id)
        return AvailabilitySlotResponse(
            slot_id=slot.slot_id,
            counselor_user_id=slot.counselor_user_id,
            counselor_name=f"{counselor.first_name} {counselor.last_name}",
            campus_id=slot.campus_id,
            campus_name=campus.campus_name,
            guidance_office_location=campus.guidance_office_location,
            delivery_mode=slot.delivery_mode,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            status=slot.status,
        )

    def appointment_response(self, appointment, actor):
        slot = self.repository.find_slot(appointment.availability_slot_id)
        details = self.slot_response(slot)
        student = self.accounts.scheduling_user(appointment.student_user_id)
        moment = utcnow()
        starts_at = db_time(slot.starts_at)
        ends_at = db_time(slot.ends_at)
        student_window = self._student_change_window_open(actor, starts_at, moment)
        has_activity = self._has_chat_activity(appointment)
        return AppointmentResponse(
            **{
                name: getattr(appointment, name)
                for name in (
                    "appointment_id",
                    "student_user_id",
                    "counselor_user_id",
                    "availability_slot_id",
                    "appointment_mode",
                    "meeting_location",
                    "concern_categories",
                    "concern_details",
                    "conversation_id",
                    "status",
                    "rejection_note",
                    "created_at",
                    "updated_at",
                )
            },
            student_name=f"{student.first_name} {student.last_name}",
            counselor_name=details.counselor_name,
            campus_id=slot.campus_id,
            campus_name=details.campus_name,
            starts_at=starts_at,
            ends_at=ends_at,
            can_cancel=appointment.status in ("PENDING", "CONFIRMED") and student_window,
            can_reschedule=appointment.status == "CONFIRMED" and student_window and not has_activity,
            can_change_mode=actor.role_code == "COUNSELOR" and appointment.status == "CONFIRMED" and moment < starts_at and not has_activity and slot.delivery_mode == "BOTH" and (appointment.appointment_mode == "FACE_TO_FACE" or bool((details.guidance_office_location or "").strip())),
        )

    def create_slots(self, actor, data):
        self.authorize(actor, ("COUNSELOR",))
        self._participants(None, actor.user_id)
        start, end = db_time(data.starts_at), db_time(data.ends_at)
        if start <= utcnow():
            raise AppError("SLOT_IN_PAST", "Availability must start in the future.")
        campus = self._campus(data.campus_id)
        if (
            data.delivery_mode != "ONLINE"
            and not (campus.guidance_office_location or "").strip()
        ):
            raise AppError(
                "GUIDANCE_OFFICE_REQUIRED",
                "Configure the campus Guidance Office location first.",
            )
        if self.repository.overlapping_slots(actor.user_id, start, end):
            raise AppError(
                "SCHEDULE_CONFLICT", "This range overlaps your existing availability."
            )
        slots = []
        duration = timedelta(minutes=data.slot_duration_minutes)
        while start < end:
            slot = AvailabilitySlot(
                counselor_user_id=actor.user_id,
                campus_id=data.campus_id,
                delivery_mode=data.delivery_mode,
                starts_at=start,
                ends_at=start + duration,
                status="AVAILABLE",
            )
            self.repository.session.add(slot)
            slots.append(slot)
            start += duration
        self.repository.session.flush()
        for slot in slots:
            self.audit.record(
                actor.user_id,
                "availability_slot_created",
                "availability_slot",
                slot.slot_id,
            )
        return [self.slot_response(slot) for slot in slots]

    def list_slots(
        self,
        actor,
        campus_id=None,
        appointment_mode=None,
        starts_after=None,
        ends_before=None,
        page=1,
        page_size=20,
        counselor_user_id=None,
    ):
        self.authorize(actor)
        if actor.role_code == "STUDENT" and counselor_user_id is not None:
            counselor = self.accounts.scheduling_user(counselor_user_id)
            if counselor is None or counselor.role_code != "COUNSELOR" or counselor.account_status != "ACTIVE":
                raise AppError("COUNSELOR_NOT_FOUND", "The selected Counselor is unavailable.", status_code=404)
        items, total = self.repository.slots(
            actor,
            utcnow(),
            campus_id,
            appointment_mode,
            db_time(starts_after) if starts_after else None,
            db_time(ends_before) if ends_before else None,
            page,
            page_size,
            counselor_user_id,
        )
        return dict(
            items=[self.slot_response(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_appointments(self, actor, status=None, page=1, page_size=20, starts_after=None, ends_before=None):
        self.authorize(actor)
        items, total = self.repository.appointments(
            actor, status, page, page_size,
            db_time(starts_after) if starts_after else None,
            db_time(ends_before) if ends_before else None,
        )
        return dict(
            items=[self.appointment_response(a, actor) for a in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def _conversation_for(self, appointment):
        if appointment.conversation_id is None:
            return None
        from app.modules.messaging.service import MessagingService

        return MessagingService(self.repository.session).for_appointment(appointment)

    def _has_chat_activity(self, appointment):
        if appointment.conversation_id is None:
            return False
        from app.modules.messaging.service import MessagingService

        return MessagingService(self.repository.session).has_activity(appointment)

    @staticmethod
    def _student_change_window_open(actor, starts_at, now):
        return actor.role_code != "STUDENT" or now <= starts_at - timedelta(hours=24)

    @staticmethod
    def _live_window(appointment, slot, moment, settings):
        """True while a confirmed ONLINE appointment's session window is open."""
        return (
            appointment.status == "CONFIRMED"
            and appointment.appointment_mode == "ONLINE"
            and slot.starts_at <= moment
            < slot.ends_at + timedelta(minutes=settings.chat_grace_minutes)
        )

    def session_response(self, actor, appointment, *, now=None):
        self.authorize(actor)
        appointment = self._owned(actor, appointment)
        slot = self.repository.find_slot(appointment.availability_slot_id)
        moment = now or utcnow()
        settings = get_settings()
        lobby_opens = slot.starts_at - timedelta(minutes=30)
        safety_deadline = slot.ends_at + timedelta(minutes=settings.chat_grace_minutes)
        conversation = self._conversation_for(appointment)
        has_activity = bool(
            conversation
            and (
                conversation.student_joined_at is not None
                or conversation.counselor_joined_at is not None
                or conversation.last_sequence_number > 0
            )
        )
        confirmed_online = (
            appointment.status == "CONFIRMED"
            and appointment.appointment_mode == "ONLINE"
        )
        live_window = self._live_window(appointment, slot, moment, settings)
        participant_joined = bool(
            conversation
            and (
                (actor.role_code == "STUDENT" and conversation.student_joined_at)
                or (actor.role_code == "COUNSELOR" and conversation.counselor_joined_at)
            )
        )
        open_conversation = bool(conversation and conversation.status == "OPEN")
        student_window = self._student_change_window_open(actor, slot.starts_at, moment)
        retention_open = bool(
            conversation
            and conversation.closed_at
            and moment < conversation.closed_at + timedelta(days=settings.chat_retention_days)
        )
        can_read_history = bool(
            conversation
            and conversation.messages_purged_at is None
            and (
                (open_conversation and live_window and participant_joined)
                or (conversation.status == "CLOSED" and actor.role_code == "COUNSELOR" and retention_open)
            )
        )
        return AppointmentSessionResponse(
            appointment_id=appointment.appointment_id,
            conversation_id=appointment.conversation_id,
            appointment_mode=appointment.appointment_mode,
            status=appointment.status,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            lobby_opens_at=lobby_opens,
            messaging_opens_at=slot.starts_at,
            safety_deadline_at=safety_deadline,
            server_time=moment,
            student_joined_at=conversation.student_joined_at if conversation else None,
            counselor_joined_at=conversation.counselor_joined_at if conversation else None,
            conversation_status=conversation.status if conversation else None,
            closure_reason=conversation.closure_reason if conversation else None,
            capabilities={
                "can_open_lobby": confirmed_online and lobby_opens <= moment < safety_deadline,
                "can_join": live_window and (conversation is None or open_conversation),
                "can_send": live_window and open_conversation and participant_joined,
                "can_read_history": can_read_history,
                "can_call": live_window,
                "can_cancel": appointment.status in ("PENDING", "CONFIRMED") and student_window,
                "can_reschedule": appointment.status == "CONFIRMED" and student_window and not has_activity,
                "can_change_mode": actor.role_code == "COUNSELOR" and appointment.status == "CONFIRMED" and moment < slot.starts_at and not has_activity and slot.delivery_mode == "BOTH" and (appointment.appointment_mode == "FACE_TO_FACE" or bool((self._campus(slot.campus_id).guidance_office_location or "").strip())),
            },
        )

    def scheduled_sessions(self, actor):
        self.authorize(actor)
        return [self.session_response(actor, item) for item in self.repository.scheduled_sessions(actor)]

    def session_detail(self, actor, appointment_id):
        return self.session_response(actor, self.repository.get(appointment_id))

    def call_context(self, actor, appointment_id, *, now=None):
        """Authorized appointment participants only; no conversation is required.

        The returned window is ephemeral. Callers must not persist SDP, ICE
        candidates, or derived call metadata (docs/AUDIO_VIDEO_CALLS.md).
        """
        self.authorize(actor)
        appointment = self._owned(actor, self.repository.get(appointment_id))
        slot = self.repository.find_slot(appointment.availability_slot_id)
        moment = now or utcnow()
        settings = get_settings()
        deadline = slot.ends_at + timedelta(minutes=settings.chat_grace_minutes)
        return CallContext(
            appointment=appointment,
            actor_role=actor.role_code,
            peer_role="COUNSELOR" if actor.role_code == "STUDENT" else "STUDENT",
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            safety_deadline_at=deadline,
            server_time=moment,
            can_call=self._live_window(appointment, slot, moment, settings),
        )

    def lock_session_appointment(self, actor, appointment_id):
        """Messaging service contract: lock and return an owned appointment."""
        self.authorize(actor)
        return self._locked_owned(actor, appointment_id)

    def session_appointment(self, actor, appointment_id):
        """Messaging service contract: return an owned appointment without locking it."""
        self.authorize(actor)
        return self._owned(actor, self.repository.get(appointment_id))

    def _owned(self, actor, appointment):
        if (
            appointment is None
            or (
                actor.role_code == "STUDENT"
                and appointment.student_user_id != actor.user_id
            )
            or (
                actor.role_code == "COUNSELOR"
                and appointment.counselor_user_id != actor.user_id
            )
        ):
            raise AppError(
                "APPOINTMENT_NOT_FOUND", "Appointment not found.", status_code=404
            )
        return appointment

    def detail(self, actor, appointment_id):
        self.authorize(actor)
        return self.appointment_response(
            self._owned(actor, self.repository.get(appointment_id)), actor
        )

    def _validate_slot(self, slot, mode, student_id, exclude_id=None):
        if slot is None or slot.status != "AVAILABLE":
            raise AppError(
                "SLOT_UNAVAILABLE", "The selected slot is no longer available."
            )
        # A slot generated from a weekly schedule disappears from calendar and
        # slot reads once that definition is disabled or deleted. Reject the
        # same stale slot here so a remembered ID cannot reserve it.
        if not self.repository.slot_schedule_is_active(slot):
            raise AppError(
                "SLOT_UNAVAILABLE", "The selected slot is no longer available."
            )
        if slot.starts_at <= utcnow():
            slot_manila_date = (
                slot.starts_at.replace(tzinfo=timezone.utc)
                .astimezone(ZoneInfo("Asia/Manila"))
                .date()
            )
            if slot_manila_date < manila_today():
                raise AppError(
                    "APPOINTMENT_DATE_PASSED",
                    "This appointment date has already passed. "
                    "Please select another available date.",
                )
            raise AppError(
                "APPOINTMENT_TIME_PASSED",
                "This appointment time is no longer available. "
                "Please select another available time.",
            )
        if slot.delivery_mode not in (mode, "BOTH"):
            raise AppError("MODE_INCOMPATIBLE", "Select a mode supported by this slot.")
        campus = self._campus(slot.campus_id)
        location = None
        if mode == "FACE_TO_FACE":
            location = (campus.guidance_office_location or "").strip()
            if not location:
                raise AppError(
                    "GUIDANCE_OFFICE_REQUIRED",
                    "The campus Guidance Office location is not configured.",
                )
        if self.repository.find_active_reservation_for_slot(
            slot.slot_id
        ) or self.repository.participant_conflict(slot, exclude_id=exclude_id):
            raise AppError(
                "SLOT_UNAVAILABLE",
                "The selected counselor is no longer available at this time.",
            )
        if self.repository.overlapping_availability_blocks(
            slot.counselor_user_id, slot.starts_at, slot.ends_at, lock=True
        ):
            raise AppError(
                "SLOT_UNAVAILABLE",
                "The counselor is unavailable during this period.",
            )
        if self.repository.participant_conflict(
            slot, student_id=student_id, exclude_id=exclude_id
        ):
            raise AppError(
                "SCHEDULE_CONFLICT", "You already have an appointment during this time."
            )
        return location

    def book(self, actor, data):
        self.authorize(actor, ("STUDENT",))
        candidate = self.repository.find_slot(data.availability_slot_id)
        if candidate is None:
            raise AppError(
                "SLOT_UNAVAILABLE", "The selected slot is no longer available."
            )
        self._participants(actor.user_id, candidate.counselor_user_id)
        slot = self.repository.find_slot(candidate.slot_id, lock=True)
        location = self._validate_slot(slot, data.appointment_mode, actor.user_id)
        slot.status = "RESERVED"
        appointment = Appointment(
            student_user_id=actor.user_id,
            counselor_user_id=slot.counselor_user_id,
            availability_slot_id=slot.slot_id,
            appointment_mode=data.appointment_mode,
            meeting_location=location,
            concern_categories=list(data.concern_categories),
            concern_details=data.concern_details,
            status="PENDING",
        )
        self.repository.add(appointment)
        self.repository.session.flush()
        self.audit.record(
            actor.user_id,
            "appointment_requested",
            "appointment",
            appointment.appointment_id,
        )
        return self.appointment_response(appointment, actor)

    def _locked_owned(self, actor, appointment_id, replacement=None):
        initial = self._owned(actor, self.repository.get(appointment_id))
        original_counselor_id = initial.counselor_user_id
        counselors = [original_counselor_id]
        if replacement:
            counselors.append(replacement.counselor_user_id)
        self._participants(initial.student_user_id, *counselors, require_active=False)
        appointment = self._owned(
            actor, self.repository.lock_appointment(appointment_id)
        )
        if appointment.counselor_user_id != original_counselor_id:
            raise AppError(
                "APPOINTMENT_CHANGED",
                "This appointment changed. Refresh and try again.",
            )
        return appointment

    def _close_appointment_conversation(self, appointment, reason):
        if appointment.conversation_id is None:
            return
        from app.modules.messaging.service import MessagingService

        MessagingService(self.repository.session).close_for_appointment(
            appointment, reason
        )

    def _complete_appointment(self, actor, appointment, slot):
        """Shared completion side effects: close chat, release slot, audit."""
        self._close_appointment_conversation(appointment, "COUNSELOR_OUTCOME")
        slot.status = "AVAILABLE"
        appointment.status = "COMPLETED"
        self.repository.session.flush()
        self.audit.record(
            actor.user_id,
            "appointment_completed",
            "appointment",
            appointment.appointment_id,
        )

    def transition(self, actor, appointment_id, action, rejection_note=None):
        self.authorize(
            actor, ("STUDENT", "COUNSELOR") if action == "cancel" else ("COUNSELOR",)
        )
        appointment = self._locked_owned(actor, appointment_id)
        allowed, target = {
            "confirm": (("PENDING",), "CONFIRMED"),
            "reject": (("PENDING",), "REJECTED"),
            "cancel": (("PENDING", "CONFIRMED"), "CANCELLED"),
            "complete": (("CONFIRMED",), "COMPLETED"),
            "no-show": (("CONFIRMED",), "NO_SHOW"),
        }[action]
        if appointment.status not in allowed:
            raise AppError(
                "INVALID_APPOINTMENT_TRANSITION",
                "This action is not available for the current appointment status.",
            )
        slot = self.repository.find_slot(appointment.availability_slot_id, lock=True)
        if action == "cancel" and not self._student_change_window_open(
            actor, slot.starts_at, utcnow()
        ):
            raise AppError(
                "APPOINTMENT_CHANGE_CUTOFF",
                "Students may cancel or reschedule until 24 hours before the appointment.",
            )
        if action == "confirm" and slot.starts_at <= utcnow():
            raise AppError(
                "SLOT_IN_PAST",
                "A request cannot be confirmed after its scheduled start.",
            )
        if action in ("complete", "no-show") and slot.starts_at > utcnow():
            raise AppError(
                "SESSION_NOT_STARTED",
                "Wait until the scheduled start to record an outcome.",
            )
        if action == "complete":
            self._complete_appointment(actor, appointment, slot)
        else:
            if target != "CONFIRMED":
                reason = (
                    "APPOINTMENT_CANCELLED"
                    if action == "cancel"
                    else "COUNSELOR_OUTCOME"
                )
                self._close_appointment_conversation(appointment, reason)
                slot.status = "AVAILABLE"
            appointment.status = target
            if action == "reject":
                appointment.rejection_note = rejection_note
            self.repository.session.flush()
            self.audit.record(
                actor.user_id,
                "appointment_" + target.lower(),
                "appointment",
                appointment.appointment_id,
            )
        return self.appointment_response(appointment, actor)

    def reschedule(self, actor, appointment_id, data):
        self.authorize(actor)
        replacement = self.repository.find_slot(data.availability_slot_id)
        if replacement is None:
            raise AppError(
                "SLOT_UNAVAILABLE", "The selected slot is no longer available."
            )
        appointment = self._locked_owned(actor, appointment_id, replacement)
        replacement_counselor = self.accounts.scheduling_user(
            replacement.counselor_user_id
        )
        if replacement_counselor.account_status != "ACTIVE":
            raise AppError(
                "PARTICIPANT_UNAVAILABLE", "The selected Counselor is unavailable."
            )
        if appointment.status != "CONFIRMED":
            raise AppError(
                "INVALID_APPOINTMENT_TRANSITION",
                "Only a confirmed appointment can be rescheduled.",
            )
        old_slot = self.repository.find_slot(appointment.availability_slot_id, lock=True)
        if not self._student_change_window_open(actor, old_slot.starts_at, utcnow()):
            raise AppError(
                "APPOINTMENT_CHANGE_CUTOFF",
                "Students may cancel or reschedule until 24 hours before the appointment.",
            )
        if self._has_chat_activity(appointment):
            raise AppError(
                "SESSION_ALREADY_ACTIVE",
                "An appointment cannot be rescheduled after a participant enters the session.",
            )
        if (
            actor.role_code == "COUNSELOR"
            and replacement.counselor_user_id != actor.user_id
        ):
            raise AppError(
                "FORBIDDEN_ROLE",
                "Select one of your own availability slots.",
                status_code=403,
            )
        old_id = appointment.availability_slot_id
        if old_id == replacement.slot_id:
            raise AppError("SLOT_UNAVAILABLE", "Choose a different available slot.")
        slots = {
            i: self.repository.find_slot(i, lock=True)
            for i in sorted([old_id, replacement.slot_id])
        }
        if appointment.conversation_id is not None:
            from app.modules.messaging.service import MessagingService

            MessagingService(self.repository.session).delete_unused_for_appointment(appointment)
        slot = slots[replacement.slot_id]
        location = self._validate_slot(
            slot,
            data.appointment_mode,
            appointment.student_user_id,
            appointment.appointment_id,
        )
        slots[old_id].status = "AVAILABLE"
        slot.status = "RESERVED"
        appointment.availability_slot_id = slot.slot_id
        appointment.counselor_user_id = slot.counselor_user_id
        appointment.appointment_mode = data.appointment_mode
        appointment.meeting_location = location
        appointment.status = "PENDING"
        appointment.rejection_note = None
        appointment.student_reminder_dispatched_at = None
        appointment.counselor_reminder_dispatched_at = None
        self.repository.session.flush()
        self.audit.record(
            actor.user_id,
            "appointment_rescheduled",
            "appointment",
            appointment.appointment_id,
        )
        return self.appointment_response(appointment, actor)

    def change_mode(self, actor, appointment_id, data):
        self.authorize(actor, ("COUNSELOR",))
        appointment = self._locked_owned(actor, appointment_id)
        if appointment.status != "CONFIRMED":
            raise AppError(
                "INVALID_APPOINTMENT_TRANSITION",
                "Only a confirmed appointment can change mode.",
            )
        slot = self.repository.find_slot(appointment.availability_slot_id, lock=True)
        if utcnow() >= slot.starts_at:
            raise AppError(
                "SESSION_ALREADY_STARTED",
                "The appointment mode cannot change after its scheduled start.",
            )
        if data.appointment_mode == appointment.appointment_mode:
            raise AppError("MODE_UNCHANGED", "Choose a different appointment mode.")
        if self._has_chat_activity(appointment):
            raise AppError(
                "SESSION_ALREADY_ACTIVE",
                "The appointment mode cannot change after a participant enters the session.",
            )
        if slot.delivery_mode not in (data.appointment_mode, "BOTH"):
            raise AppError("MODE_INCOMPATIBLE", "Select a mode supported by this slot.")
        location = None
        if data.appointment_mode == "FACE_TO_FACE":
            campus = self._campus(slot.campus_id)
            location = (campus.guidance_office_location or "").strip()
            if not location:
                raise AppError(
                    "GUIDANCE_OFFICE_REQUIRED",
                    "The campus Guidance Office location is not configured.",
                )
        if appointment.conversation_id is not None:
            from app.modules.messaging.service import MessagingService

            MessagingService(self.repository.session).delete_unused_for_appointment(appointment)
        appointment.appointment_mode = data.appointment_mode
        appointment.meeting_location = location
        appointment.student_reminder_dispatched_at = None
        appointment.counselor_reminder_dispatched_at = None
        self.repository.session.flush()
        self.audit.record(
            actor.user_id,
            "appointment_mode_changed",
            "appointment",
            appointment.appointment_id,
        )
        return self.appointment_response(appointment, actor)

    # ------------------------------------------------ session records/files

    RECORD_FIELDS = ("presenting_concern", "session_summary", "intervention", "plan")
    RECORD_WRITABLE_STATUSES = ("CONFIRMED", "COMPLETED")
    SESSION_FILE_TYPES = {
        ".pdf": ("application/pdf", "pdf"),
        ".jpg": ("image/jpeg", "jpg"),
        ".jpeg": ("image/jpeg", "jpg"),
        ".png": ("image/png", "png"),
    }

    def _record_writable(self, appointment) -> bool:
        return appointment.status in self.RECORD_WRITABLE_STATUSES

    def _finalize_record(self, actor, record):
        record.status = "FINAL"
        record.finalized_at = utcnow()
        self.audit.record(
            actor.user_id, "session_record_finalized", "session_record", record.record_id
        )

    def _record_response(self, actor, appointment, record):
        counselor = actor.role_code == "COUNSELOR"
        if not counselor and (
            record is None
            or record.status != "FINAL"
            or appointment.status != "COMPLETED"
        ):
            raise AppError(
                "RECORD_NOT_FOUND",
                "No final session record is available.",
                status_code=404,
            )
        can_edit = (
            counselor
            and self._record_writable(appointment)
            and (record is None or record.status == "DRAFT")
        )
        values = {
            field: getattr(record, field, None)
            for field in ("notepad", *self.RECORD_FIELDS, "follow_up_on")
        }
        if not counselor:
            values["notepad"] = None
        return SessionRecordResponse(
            appointment_id=appointment.appointment_id,
            record_id=record.record_id if record is not None else None,
            status=record.status if record is not None else "DRAFT",
            finalized_at=record.finalized_at if record is not None else None,
            updated_at=record.updated_at if record is not None else None,
            can_edit=can_edit,
            can_finalize=can_edit,
            can_reopen=bool(
                counselor
                and record is not None
                and record.status == "FINAL"
                and appointment.status in ("CONFIRMED", "COMPLETED")
            ),
            **values,
        )

    def get_session_record(self, actor, appointment_id):
        self.authorize(actor)
        appointment = self._owned(actor, self.repository.get(appointment_id))
        return self._record_response(
            actor, appointment, self.repository.session_record(appointment_id)
        )

    def save_session_record(self, actor, appointment_id, data: SessionRecordUpdateRequest):
        self.authorize(actor, ("COUNSELOR",))
        appointment = self._owned(actor, self.repository.get(appointment_id))
        if not self._record_writable(appointment):
            raise AppError(
                "RECORD_NOT_EDITABLE",
                "The record can be edited only for confirmed or completed sessions.",
                status_code=409,
            )
        record = self.repository.session_record(appointment_id, lock=True)
        if record is not None and record.status == "FINAL":
            raise AppError(
                "RECORD_FINALIZED", "The finalized record is read-only.", status_code=409
            )
        if record is None:
            record = SessionRecord(
                appointment_id=appointment.appointment_id,
                counselor_user_id=actor.user_id,
            )
            self.repository.add(record)
        for field in ("notepad", *self.RECORD_FIELDS, "follow_up_on"):
            setattr(record, field, getattr(data, field))
        self.repository.session.flush()
        return self._record_response(actor, appointment, record)

    def finalize_session_record(self, actor, appointment_id):
        self.authorize(actor, ("COUNSELOR",))
        appointment = self._owned(actor, self.repository.get(appointment_id))
        if not self._record_writable(appointment):
            raise AppError(
                "RECORD_NOT_EDITABLE",
                "The record can be edited only for confirmed or completed sessions.",
                status_code=409,
            )
        record = self.repository.session_record(appointment_id, lock=True)
        if record is None:
            raise AppError(
                "RECORD_NOT_SAVED", "Save the record before finalizing it.", status_code=409
            )
        if record.status == "FINAL":
            raise AppError("RECORD_ALREADY_FINAL", "The record is already finalized.", status_code=409)
        missing = [field for field in self.RECORD_FIELDS if not (getattr(record, field) or "").strip()]
        if missing:
            raise AppError(
                "RECORD_INCOMPLETE",
                "Complete every assessment field before finalizing.",
                details={"fields": missing},
                status_code=409,
            )
        self._finalize_record(actor, record)
        self.repository.session.flush()
        return self._record_response(actor, appointment, record)

    def mark_session_done(self, actor, appointment_id):
        """Finalize the assessment (if needed) and complete the appointment atomically."""
        self.authorize(actor, ("COUNSELOR",))
        appointment = self._locked_owned(actor, appointment_id)
        if appointment.status != "CONFIRMED":
            raise AppError(
                "INVALID_APPOINTMENT_TRANSITION",
                "This action is not available for the current appointment status.",
            )
        slot = self.repository.find_slot(appointment.availability_slot_id, lock=True)
        if slot.starts_at > utcnow():
            raise AppError(
                "SESSION_NOT_STARTED",
                "Wait until the scheduled start to record an outcome.",
            )
        record = self.repository.session_record(appointment_id, lock=True)
        if record is None:
            raise AppError(
                "RECORD_NOT_SAVED",
                "Open the session record and complete the assessment before marking the session done.",
                status_code=409,
            )
        if record.status == "DRAFT":
            missing = [
                field
                for field in self.RECORD_FIELDS
                if not (getattr(record, field) or "").strip()
            ]
            if missing:
                raise AppError(
                    "RECORD_INCOMPLETE",
                    "Complete every assessment field before marking the session done.",
                    details={"fields": missing},
                    status_code=409,
                )
            self._finalize_record(actor, record)
        self._complete_appointment(actor, appointment, slot)
        return appointment

    def reopen_session_record(self, actor, appointment_id):
        self.authorize(actor, ("COUNSELOR",))
        appointment = self._owned(actor, self.repository.get(appointment_id))
        record = self.repository.session_record(appointment_id, lock=True)
        if (
            record is None
            or record.status != "FINAL"
            or appointment.status not in ("CONFIRMED", "COMPLETED")
        ):
            raise AppError(
                "RECORD_NOT_REOPENABLE",
                "Only a finalized record for a confirmed or completed session can be reopened.",
                status_code=409,
            )
        record.status = "DRAFT"
        record.finalized_at = None
        self.audit.record(
            actor.user_id, "session_record_reopened", "session_record", record.record_id
        )
        self.repository.session.flush()
        return self._record_response(actor, appointment, record)

    def _validate_session_file(self, content: bytes, filename: str) -> tuple[str, str]:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in self.SESSION_FILE_TYPES:
            raise AppError(
                "SESSION_FILE_TYPE_INVALID",
                "Upload a PDF, JPEG, or PNG file.",
                status_code=422,
            )
        mime, ext = self.SESSION_FILE_TYPES[suffix]
        if not content:
            raise AppError("SESSION_FILE_EMPTY", "The selected file is empty.", status_code=422)
        max_bytes = get_settings().session_document_max_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise AppError(
                "SESSION_FILE_TOO_LARGE",
                f"Files must be at most {get_settings().session_document_max_mb} MB.",
                status_code=422,
            )
        if mime == "application/pdf":
            if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
                raise AppError(
                    "SESSION_FILE_INVALID", "The file is not a valid PDF.", status_code=422
                )
        else:
            try:
                from PIL import Image

                with Image.open(io.BytesIO(content)) as image:
                    image.verify()
            except Exception:
                raise AppError(
                    "SESSION_FILE_INVALID", "The file is not a valid image.", status_code=422
                ) from None
        return mime, ext

    def _session_storage_path(self, storage_key: str) -> Path:
        root = Path(get_settings().session_document_storage_root).resolve()
        target = (root / storage_key).resolve()
        if not target.is_relative_to(root) or target == root:
            raise OSError("Invalid private storage key")
        return target

    def _store_session_bytes(self, content: bytes, ext: str) -> str:
        # ponytail: no crash-recovery marker; an unreferenced file after a failed
        # commit is harmless and never served. Add a sweep job if orphans matter.
        key = f"session/{uuid.uuid4().hex}.{ext}"
        target = self._session_storage_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def _delete_session_bytes(self, storage_key: str) -> bool:
        try:
            self._session_storage_path(storage_key).unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _document_response(self, actor, document, uploader_name):
        return SessionDocumentResponse(
            document_id=document.document_id,
            appointment_id=document.appointment_id,
            uploader_user_id=document.uploader_user_id,
            uploader_name=uploader_name,
            original_filename=document.original_filename,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            created_at=document.created_at,
            can_delete=actor.role_code == "COUNSELOR"
            or document.uploader_user_id == actor.user_id,
        )

    def _assert_document_access(self, actor, appointment):
        if actor.role_code == "STUDENT" and appointment.status != "COMPLETED":
            raise AppError(
                "DOCUMENT_ACCESS_CLOSED",
                "Session files open after the Counselor marks the session completed.",
                status_code=409,
            )

    def list_session_documents(self, actor, appointment_id):
        self.authorize(actor)
        appointment = self._owned(actor, self.repository.get(appointment_id))
        self._assert_document_access(actor, appointment)
        return [
            self._document_response(
                actor, document, f"{first_name} {last_name}".strip()
            )
            for document, first_name, last_name in self.repository.session_documents(appointment_id)
        ]

    def upload_session_document(self, actor, appointment_id, content, filename):
        self.authorize(actor)
        appointment = self._owned(actor, self.repository.get(appointment_id))
        self._assert_document_access(actor, appointment)
        if not self._record_writable(appointment):
            raise AppError(
                "DOCUMENT_UPLOAD_CLOSED",
                "Files can be added only for confirmed or completed sessions.",
                status_code=409,
            )
        mime, ext = self._validate_session_file(content, filename)
        safe_name = (Path(filename or "").name or f"session-file.{ext}").strip()[:255]
        storage_key = self._store_session_bytes(content, ext)
        document = SessionDocument(
            appointment_id=appointment.appointment_id,
            uploader_user_id=actor.user_id,
            original_filename=safe_name,
            mime_type=mime,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).digest(),
            storage_key=storage_key,
        )
        self.repository.add(document)
        try:
            self.repository.session.flush()
            self.audit.record(
                actor.user_id, "session_document_uploaded", "session_document", document.document_id
            )
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            self._delete_session_bytes(storage_key)
            raise
        return self._document_response(
            actor, document, f"{actor.first_name} {actor.last_name}".strip()
        )

    def download_session_document(self, actor, appointment_id, document_id):
        self.authorize(actor)
        appointment = self._owned(actor, self.repository.get(appointment_id))
        self._assert_document_access(actor, appointment)
        document = self.repository.session_document(appointment_id, document_id)
        if document is None or document.deleted_at is not None:
            raise AppError("DOCUMENT_NOT_FOUND", "File not found.", status_code=404)
        try:
            content = self._session_storage_path(document.storage_key).read_bytes()
        except OSError:
            raise AppError("DOCUMENT_NOT_FOUND", "File not found.", status_code=404) from None
        self.audit.record(
            actor.user_id, "session_document_downloaded", "session_document", document.document_id
        )
        return content, document.mime_type, document.original_filename

    def delete_session_document(self, actor, appointment_id, document_id):
        self.authorize(actor)
        appointment = self._owned(actor, self.repository.get(appointment_id))
        self._assert_document_access(actor, appointment)
        document = self.repository.session_document(appointment_id, document_id, lock=True)
        if document is None or document.deleted_at is not None:
            raise AppError("DOCUMENT_NOT_FOUND", "File not found.", status_code=404)
        if actor.role_code != "COUNSELOR" and document.uploader_user_id != actor.user_id:
            raise AppError(
                "DOCUMENT_DELETE_FORBIDDEN", "You cannot delete this file.", status_code=403
            )
        document.deleted_at = utcnow()
        document.deleted_by_user_id = actor.user_id
        self.audit.record(
            actor.user_id, "session_document_deleted", "session_document", document.document_id
        )
        self.repository.session.commit()
        if not self._delete_session_bytes(document.storage_key):
            logger.warning("session_document_cleanup_retry_required")


def get_appointments_service(session: Session = Depends(get_session)):
    return AppointmentsService(session)
