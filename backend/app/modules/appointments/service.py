"""appointments service: authorization + business rules.

Core rules (docs/APPOINTMENT_SCHEDULING.md, ARCHITECTURE.md):
- Counselor-owned concrete slots; FACE_TO_FACE-capable slots require the
  campus guidance_office_location, snapshotted immutably into
  appointments.meeting_location at booking time.
- Booking: verify active student, slot AVAILABLE, mode compatibility ->
  reserve slot + create PENDING appointment in ONE transaction.
- A confirmed ONLINE appointment gets exactly one dedicated APPOINTMENT
  conversation at its scheduled start — requested through the MESSAGING
  service (never by creating message records directly).

# TODO: Timing/cutoffs/reminders are pending ADR-P04.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import AppointmentsRepository


class AppointmentsService(BaseService[Appointment]):
    """Scheduling business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(AppointmentsRepository(session))


def get_appointments_service(session: Session = Depends(get_session)) -> AppointmentsService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return AppointmentsService(session)
