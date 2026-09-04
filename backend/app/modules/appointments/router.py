"""appointments router (thin HTTP transport).

Action endpoints per NAMING_CONVENTIONS.md, e.g.:
POST /appointments/{appointment_id}/confirm
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.appointments.service import AppointmentsService, get_appointments_service

router = APIRouter(prefix="/appointments", tags=["appointments"])
