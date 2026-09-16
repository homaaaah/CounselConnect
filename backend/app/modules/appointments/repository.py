"""Scheduling persistence. Locking reads see current committed MySQL state."""

from datetime import timedelta

from sqlalchemy import func, select

from app.modules.bases import BaseRepository
from app.modules.appointments.models import (
    Appointment,
    AvailabilitySlot,
    CounselorAvailabilityBlock,
    CounselorBlockedDate,
    CounselorWeeklySchedule,
)


class AppointmentsRepository(BaseRepository[Appointment]):
    model = Appointment

    # Weekly TIME values are university-local configuration. The service must
    # reject overlapping schedule periods and partial final slots.
    def create_weekly_schedule(self, **values):
        schedule = CounselorWeeklySchedule(**values)
        self.session.add(schedule)
        return schedule

    def weekly_schedules(self, counselor_id, *, active_only=False):
        stmt = select(CounselorWeeklySchedule).where(
            CounselorWeeklySchedule.counselor_user_id == counselor_id
        )
        if active_only:
            stmt = stmt.where(CounselorWeeklySchedule.is_active.is_(True))
        return list(self.session.scalars(stmt.order_by(
            CounselorWeeklySchedule.day_of_week,
            CounselorWeeklySchedule.start_time,
            CounselorWeeklySchedule.weekly_schedule_id,
        )))

    def active_weekly_schedules(self, counselor_id=None):
        stmt = select(CounselorWeeklySchedule).where(CounselorWeeklySchedule.is_active.is_(True))
        if counselor_id is not None:
            stmt = stmt.where(CounselorWeeklySchedule.counselor_user_id == counselor_id)
        return list(self.session.scalars(stmt))

    def deactivate_weekly_schedule(self, counselor_id, weekly_schedule_id):
        schedule = self.lock_weekly_schedule(counselor_id, weekly_schedule_id)
        if schedule:
            schedule.is_active = False
        return schedule

    def lock_weekly_schedule(self, counselor_id, weekly_schedule_id):
        return self.session.scalar(
            select(CounselorWeeklySchedule)
            .where(
                CounselorWeeklySchedule.counselor_user_id == counselor_id,
                CounselorWeeklySchedule.weekly_schedule_id == weekly_schedule_id,
            )
            .with_for_update()
        )

    def matching_weekly_schedule(self, counselor_id, data, *, exclude_id=None):
        stmt = select(CounselorWeeklySchedule).where(
            CounselorWeeklySchedule.counselor_user_id == counselor_id,
            CounselorWeeklySchedule.campus_id == data.campus_id,
            CounselorWeeklySchedule.day_of_week == data.day_of_week,
            CounselorWeeklySchedule.start_time == data.start_time,
            CounselorWeeklySchedule.end_time == data.end_time,
            CounselorWeeklySchedule.slot_duration_minutes == data.slot_duration_minutes,
            CounselorWeeklySchedule.delivery_mode == data.delivery_mode,
        )
        if exclude_id is not None:
            stmt = stmt.where(CounselorWeeklySchedule.weekly_schedule_id != exclude_id)
        return self.session.scalar(stmt.limit(1).with_for_update())

    def overlapping_weekly_schedule(self, counselor_id, day_of_week, start_time, end_time, *, exclude_id=None):
        stmt = select(CounselorWeeklySchedule).where(
            CounselorWeeklySchedule.counselor_user_id == counselor_id,
            CounselorWeeklySchedule.day_of_week == day_of_week,
            CounselorWeeklySchedule.is_active.is_(True),
            CounselorWeeklySchedule.start_time < end_time,
            CounselorWeeklySchedule.end_time > start_time,
        )
        if exclude_id is not None:
            stmt = stmt.where(CounselorWeeklySchedule.weekly_schedule_id != exclude_id)
        return self.session.scalar(stmt.limit(1).with_for_update())

    def create_availability_block(self, **values):
        block = CounselorAvailabilityBlock(**values)
        self.session.add(block)
        return block

    def availability_blocks(self, counselor_id):
        return list(self.session.scalars(
            select(CounselorAvailabilityBlock)
            .where(CounselorAvailabilityBlock.counselor_user_id == counselor_id)
            .order_by(
                CounselorAvailabilityBlock.starts_at,
                CounselorAvailabilityBlock.availability_block_id,
            )
        ))

    def delete_availability_block(self, counselor_id, availability_block_id):
        block = self.session.scalar(
            select(CounselorAvailabilityBlock)
            .where(
                CounselorAvailabilityBlock.counselor_user_id == counselor_id,
                CounselorAvailabilityBlock.availability_block_id == availability_block_id,
            )
            .with_for_update()
        )
        if block:
            self.session.delete(block)
        return block

    def overlapping_availability_blocks(self, counselor_id, starts_at, ends_at, *, lock=False):
        stmt = (
            select(CounselorAvailabilityBlock)
            .where(
                CounselorAvailabilityBlock.counselor_user_id == counselor_id,
                CounselorAvailabilityBlock.starts_at < ends_at,
                CounselorAvailabilityBlock.ends_at > starts_at,
            )
            .order_by(CounselorAvailabilityBlock.starts_at, CounselorAvailabilityBlock.availability_block_id)
        )
        if lock:
            stmt = stmt.with_for_update()
        return list(self.session.scalars(stmt))

    def overlapping_active_appointments(self, counselor_id, starts_at, ends_at):
        return list(self.session.scalars(
            select(Appointment)
            .join(AvailabilitySlot, Appointment.availability_slot_id == AvailabilitySlot.slot_id)
            .where(
                Appointment.counselor_user_id == counselor_id,
                Appointment.status.in_(["PENDING", "CONFIRMED"]),
                AvailabilitySlot.starts_at < ends_at,
                AvailabilitySlot.ends_at > starts_at,
            )
            .order_by(AvailabilitySlot.starts_at, Appointment.appointment_id)
        ))

    def blocked_date(self, counselor_id, blocked_date, *, lock=False):
        stmt = select(CounselorBlockedDate).where(CounselorBlockedDate.counselor_user_id == counselor_id, CounselorBlockedDate.blocked_date == blocked_date)
        return self.session.scalar(stmt.with_for_update() if lock else stmt)

    def blocked_dates(self, counselor_ids, start_date, end_date):
        return set(self.session.scalars(select(CounselorBlockedDate.blocked_date).where(CounselorBlockedDate.counselor_user_id.in_(counselor_ids), CounselorBlockedDate.blocked_date >= start_date, CounselorBlockedDate.blocked_date <= end_date)))

    def active_counselor_ids(self):
        from app.modules.accounts.models import User
        return list(self.session.scalars(select(User.user_id).where(User.role_code == "COUNSELOR", User.account_status == "ACTIVE")))

    def add_blocked_date(self, counselor_id, blocked_date, reason=None):
        block = CounselorBlockedDate(counselor_user_id=counselor_id, blocked_date=blocked_date, reason=reason)
        self.session.add(block)
        return block

    def remove_blocked_date(self, counselor_id, blocked_date):
        block = self.blocked_date(counselor_id, blocked_date, lock=True)
        if block:
            self.session.delete(block)
        return block

    def find_slot(self, slot_id, *, lock=False):
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.slot_id == slot_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(stmt)

    def find_slot_exact(self, counselor_id, campus_id, starts_at, ends_at):
        return self.session.scalar(select(AvailabilitySlot).where(
            AvailabilitySlot.counselor_user_id == counselor_id,
            AvailabilitySlot.campus_id == campus_id,
            AvailabilitySlot.starts_at == starts_at,
            AvailabilitySlot.ends_at == ends_at,
        ))

    def lock_appointment(self, appointment_id):
        return self.session.scalar(
            select(Appointment)
            .where(Appointment.appointment_id == appointment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def overlapping_slots(self, counselor_id, starts_at, ends_at):
        return self.session.scalar(
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.counselor_user_id == counselor_id,
                AvailabilitySlot.starts_at < ends_at,
                AvailabilitySlot.ends_at > starts_at,
            )
            .limit(1)
            .with_for_update()
        )

    def participant_conflict(self, slot, *, student_id=None, exclude_id=None):
        scope = (
            Appointment.student_user_id == student_id
            if student_id is not None
            else Appointment.counselor_user_id == slot.counselor_user_id
        )
        stmt = (
            select(Appointment)
            .join(
                AvailabilitySlot,
                Appointment.availability_slot_id == AvailabilitySlot.slot_id,
            )
            .where(
                scope,
                Appointment.status.in_(["PENDING", "CONFIRMED"]),
                AvailabilitySlot.starts_at < slot.ends_at,
                AvailabilitySlot.ends_at > slot.starts_at,
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(Appointment.appointment_id != exclude_id)
        return self.session.scalar(stmt.limit(1).with_for_update())

    def find_active_reservation_for_slot(self, slot_id):
        return self.session.scalar(
            select(Appointment)
            .where(Appointment.active_reservation_slot_id == slot_id)
            .with_for_update()
        )

    def page(self, stmt, page, page_size):
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        items = list(
            self.session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
        )
        return items, total

    def calendar_slots(self, counselor_ids, now, starts_after, ends_before):
        """All unreserved calendar starts, without the slot list's pagination."""
        # A replaced weekly schedule is retained for audit/history, but its
        # leftover AVAILABLE slots must no longer appear. Concrete one-off
        # slots have no weekly_schedule_id and remain available as created.
        active_weekly_schedule = select(CounselorWeeklySchedule.weekly_schedule_id).where(
            CounselorWeeklySchedule.weekly_schedule_id == AvailabilitySlot.weekly_schedule_id,
            CounselorWeeklySchedule.is_active.is_(True),
        ).exists()
        blocked_by_time = select(CounselorAvailabilityBlock.availability_block_id).where(
            CounselorAvailabilityBlock.counselor_user_id == AvailabilitySlot.counselor_user_id,
            CounselorAvailabilityBlock.starts_at < AvailabilitySlot.ends_at,
            CounselorAvailabilityBlock.ends_at > AvailabilitySlot.starts_at,
        ).exists()
        return list(self.session.scalars(
            select(AvailabilitySlot).where(
                AvailabilitySlot.counselor_user_id.in_(counselor_ids),
                AvailabilitySlot.status == "AVAILABLE",
                AvailabilitySlot.starts_at > now,
                AvailabilitySlot.starts_at >= starts_after,
                AvailabilitySlot.starts_at < ends_before,
                (AvailabilitySlot.weekly_schedule_id.is_(None) | active_weekly_schedule),
                ~blocked_by_time,
            ).order_by(AvailabilitySlot.starts_at)
        ))

    def slots(
        self,
        actor,
        now,
        campus_id,
        appointment_mode,
        starts_after,
        ends_before,
        page,
        page_size,
    ):
        # Filter before count/offset/limit so every page and its total describe
        # the same visible slots. Fixed offsets avoid requiring MySQL timezone
        # tables; persisted timestamps are UTC and Manila is UTC+08:00.
        active_weekly_schedule = select(CounselorWeeklySchedule.weekly_schedule_id).where(
            CounselorWeeklySchedule.weekly_schedule_id == AvailabilitySlot.weekly_schedule_id,
            CounselorWeeklySchedule.is_active.is_(True),
        ).exists()
        blocked_by_date = select(CounselorBlockedDate.blocked_date_id).where(
            CounselorBlockedDate.counselor_user_id == AvailabilitySlot.counselor_user_id,
            CounselorBlockedDate.blocked_date == func.date(
                func.convert_tz(AvailabilitySlot.starts_at, "+00:00", "+08:00")
            ),
        ).exists()
        blocked_by_time = select(CounselorAvailabilityBlock.availability_block_id).where(
            CounselorAvailabilityBlock.counselor_user_id == AvailabilitySlot.counselor_user_id,
            CounselorAvailabilityBlock.starts_at < AvailabilitySlot.ends_at,
            CounselorAvailabilityBlock.ends_at > AvailabilitySlot.starts_at,
        ).exists()
        stmt = select(AvailabilitySlot).where(
            AvailabilitySlot.starts_at > now,
            (AvailabilitySlot.weekly_schedule_id.is_(None) | active_weekly_schedule),
            ~blocked_by_date,
            ~blocked_by_time,
        )
        if actor.role_code == "COUNSELOR":
            stmt = stmt.where(AvailabilitySlot.counselor_user_id == actor.user_id)
        else:
            stmt = stmt.where(AvailabilitySlot.status == "AVAILABLE")
        if campus_id is not None:
            stmt = stmt.where(AvailabilitySlot.campus_id == campus_id)
        if appointment_mode:
            stmt = stmt.where(
                AvailabilitySlot.delivery_mode.in_([appointment_mode, "BOTH"])
            )
        if starts_after:
            stmt = stmt.where(AvailabilitySlot.starts_at >= starts_after)
        if ends_before:
            stmt = stmt.where(AvailabilitySlot.ends_at <= ends_before)
        return self.page(
            stmt.order_by(AvailabilitySlot.starts_at, AvailabilitySlot.slot_id),
            page,
            page_size,
        )

    def appointments(self, actor, status, page, page_size):
        scope = (
            Appointment.student_user_id
            if actor.role_code == "STUDENT"
            else Appointment.counselor_user_id
        )
        stmt = select(Appointment).where(scope == actor.user_id)
        if status:
            stmt = stmt.where(Appointment.status == status)
        return self.page(
            stmt.order_by(
                Appointment.created_at.desc(), Appointment.appointment_id.desc()
            ),
            page,
            page_size,
        )

    def scheduled_sessions(self, actor):
        scope = (
            Appointment.student_user_id
            if actor.role_code == "STUDENT"
            else Appointment.counselor_user_id
        )
        return list(self.session.scalars(
            select(Appointment)
            .join(AvailabilitySlot, Appointment.availability_slot_id == AvailabilitySlot.slot_id)
            .where(
                scope == actor.user_id,
                Appointment.appointment_mode == "ONLINE",
                Appointment.status == "CONFIRMED",
            )
            .order_by(AvailabilitySlot.starts_at, Appointment.appointment_id)
        ))

    def reminder_candidates(self, now):
        window_end = now + timedelta(minutes=30)
        return list(self.session.execute(
            select(Appointment, AvailabilitySlot)
            .join(AvailabilitySlot, Appointment.availability_slot_id == AvailabilitySlot.slot_id)
            .where(
                Appointment.status == "CONFIRMED",
                Appointment.appointment_mode == "ONLINE",
                AvailabilitySlot.starts_at > now,
                AvailabilitySlot.starts_at <= window_end,
                (
                    Appointment.student_reminder_dispatched_at.is_(None)
                    | Appointment.counselor_reminder_dispatched_at.is_(None)
                ),
            )
            .order_by(AvailabilitySlot.starts_at, Appointment.appointment_id)
            .limit(100)
        ))

    def timeout_candidates(self, cutoff):
        return list(self.session.execute(
            select(Appointment, AvailabilitySlot)
            .join(AvailabilitySlot, Appointment.availability_slot_id == AvailabilitySlot.slot_id)
            .where(
                Appointment.status == "CONFIRMED",
                Appointment.appointment_mode == "ONLINE",
                Appointment.conversation_id.is_not(None),
                AvailabilitySlot.ends_at <= cutoff,
            )
            .order_by(AvailabilitySlot.ends_at, Appointment.appointment_id)
            .limit(100)
        ))
