"""Scheduling persistence. Locking reads see current committed MySQL state."""

from sqlalchemy import func, select

from app.modules.bases import BaseRepository
from app.modules.appointments.models import Appointment, AvailabilitySlot


class AppointmentsRepository(BaseRepository[Appointment]):
    model = Appointment

    def find_slot(self, slot_id, *, lock=False):
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.slot_id == slot_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(stmt)

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
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.starts_at > now)
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
