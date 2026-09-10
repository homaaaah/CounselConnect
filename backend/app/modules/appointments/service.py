"""Atomic scheduling workflow from Flowchart V1, page 4."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database import get_session
from app.modules.accounts.service import AccountsService
from app.modules.audit.service import AuditService
from app.modules.bases import BaseService
from app.modules.appointments.models import (
    Appointment,
    AvailabilitySlot,
    CounselorAvailabilityBlock,
    CounselorWeeklySchedule,
)
from app.modules.appointments.repository import AppointmentsRepository
from app.modules.appointments.schemas import (
    AppointmentResponse,
    AvailabilitySlotResponse,
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def manila_today():
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def db_time(value):
    return (
        value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    )


class AppointmentsService(BaseService[Appointment]):
    def __init__(self, session: Session):
        super().__init__(AppointmentsRepository(session))
        self.accounts = AccountsService(session)
        self.audit = AuditService(session)

    def ensure_schedule_slots(self, start_date, end_date, counselor_id=None):
        """Materialize only the searched dates from active weekly schedules."""
        schedules = self.repository.active_weekly_schedules(counselor_id)
        created = 0
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
                    if not self.repository.overlapping_availability_blocks(schedule.counselor_user_id, start, end) and not self.repository.find_slot_exact(schedule.counselor_user_id, schedule.campus_id, start, end):
                        self.repository.session.add(AvailabilitySlot(counselor_user_id=schedule.counselor_user_id, campus_id=schedule.campus_id, delivery_mode=schedule.delivery_mode, starts_at=start, ends_at=end, status="AVAILABLE", weekly_schedule_id=schedule.weekly_schedule_id))
                        created += 1
                    local_start += duration
        if created:
            self.repository.session.flush()

    def calendar(self, actor, start_date: date, end_date: date):
        self.authorize(actor)
        if end_date < start_date or (end_date - start_date).days > 62:
            raise AppError("INVALID_CALENDAR_RANGE", "Choose a calendar range of 63 days or less.", status_code=422)
        self.ensure_schedule_slots(start_date, end_date, actor.user_id if actor.role_code == "COUNSELOR" else None)
        counselor_ids = [actor.user_id] if actor.role_code == "COUNSELOR" else self.repository.active_counselor_ids()
        blocked = self.repository.blocked_dates(counselor_ids, start_date, end_date) if counselor_ids else set()
        days = []
        for offset in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=offset)
            weekday = day.weekday() < 5
            is_blocked = day in blocked
            days.append({"calendar_date": day, "is_weekday": weekday, "is_blocked": is_blocked,
                "available_times": [] if not weekday or is_blocked else [f"{hour:02d}:00" for hour in range(8, 16)]})
        return {"timezone": "Asia/Manila", "business_hours": "Monday-Friday, 8:00 AM-4:00 PM", "days": days}

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
        campus = self._campus(data.campus_id)
        if data.delivery_mode != "ONLINE" and not (campus.guidance_office_location or "").strip():
            raise AppError("GUIDANCE_OFFICE_REQUIRED", "Configure the campus Guidance Office location first.")
        if self.repository.overlapping_weekly_schedule(
            actor.user_id, data.day_of_week, data.start_time, data.end_time
        ):
            raise AppError("SCHEDULE_CONFLICT", "This weekly period overlaps an active schedule.")
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

    def list_weekly_schedules(self, actor):
        self.authorize(actor, ("COUNSELOR",))
        return self.repository.weekly_schedules(actor.user_id)

    def list_availability_blocks(self, actor):
        self.authorize(actor, ("COUNSELOR",))
        return self.repository.availability_blocks(actor.user_id)

    def deactivate_weekly_schedule(self, actor, weekly_schedule_id):
        self.authorize(actor, ("COUNSELOR",))
        schedule = self.repository.deactivate_weekly_schedule(actor.user_id, weekly_schedule_id)
        if schedule is None:
            raise AppError("SCHEDULE_NOT_FOUND", "Weekly schedule not found.", status_code=404)
        self.audit.record(actor.user_id, "weekly_schedule_deactivated", "counselor_weekly_schedule", schedule.weekly_schedule_id)

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

    def appointment_response(self, appointment):
        slot = self.repository.find_slot(appointment.availability_slot_id)
        details = self.slot_response(slot)
        student = self.accounts.scheduling_user(appointment.student_user_id)
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
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
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
    ):
        self.authorize(actor)
        items, total = self.repository.slots(
            actor,
            utcnow(),
            campus_id,
            appointment_mode,
            db_time(starts_after) if starts_after else None,
            db_time(ends_before) if ends_before else None,
            page,
            page_size,
        )
        counselor_ids = {slot.counselor_user_id for slot in items}
        if counselor_ids:
            blocked = self.repository.blocked_dates(counselor_ids, manila_today(), manila_today() + timedelta(days=370))
            # Time-range availability blocks exclude matching slots for both roles.
            time_blocks = [
                block
                for counselor_id in counselor_ids
                for block in self.repository.overlapping_availability_blocks(
                    counselor_id,
                    min(slot.starts_at for slot in items),
                    max(slot.ends_at for slot in items),
                )
            ]
            def blocked_by_time_range(slot):
                return any(
                    block.counselor_user_id == slot.counselor_user_id
                    and block.starts_at < slot.ends_at
                    and block.ends_at > slot.starts_at
                    for block in time_blocks
                )
            items = [
                slot
                for slot in items
                if slot.starts_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date() not in blocked
                and not blocked_by_time_range(slot)
            ]
            total = len(items)
        return dict(
            items=[self.slot_response(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_appointments(self, actor, status=None, page=1, page_size=20):
        self.authorize(actor)
        items, total = self.repository.appointments(actor, status, page, page_size)
        return dict(
            items=[self.appointment_response(a) for a in items],
            total=total,
            page=page,
            page_size=page_size,
        )

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
            self._owned(actor, self.repository.get(appointment_id))
        )

    def _validate_slot(self, slot, mode, student_id, exclude_id=None):
        if slot is None or slot.status != "AVAILABLE" or slot.starts_at <= utcnow():
            raise AppError(
                "SLOT_UNAVAILABLE", "The selected slot is no longer available."
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
        return self.appointment_response(appointment)

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
        if target != "CONFIRMED":
            if appointment.conversation_id is not None:
                from app.modules.messaging.service import MessagingService

                MessagingService(self.repository.session).close_for_appointment(
                    appointment
                )
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
        return self.appointment_response(appointment)

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
        if appointment.conversation_id is not None:
            raise AppError(
                "SESSION_ALREADY_LINKED",
                "An appointment with a linked session cannot be rescheduled.",
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
        self.repository.session.flush()
        self.audit.record(
            actor.user_id,
            "appointment_rescheduled",
            "appointment",
            appointment.appointment_id,
        )
        return self.appointment_response(appointment)


def get_appointments_service(session: Session = Depends(get_session)):
    return AppointmentsService(session)
