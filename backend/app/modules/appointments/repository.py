"""appointments repository (persistence only)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.appointments.models import Appointment, AvailabilitySlot


class AppointmentsRepository(BaseRepository[Appointment]):
    """Owns all scheduling-domain SQLAlchemy queries."""

    model = Appointment

    def find_slot(self, slot_id: int) -> AvailabilitySlot | None:
        return self.session.get(AvailabilitySlot, slot_id)

    def find_active_reservation_for_slot(self, slot_id: int) -> Appointment | None:
        """Double-booking check using the v4 generated-column guard."""
        return self.session.scalar(
            select(Appointment).where(Appointment.active_reservation_slot_id == slot_id)
        )
