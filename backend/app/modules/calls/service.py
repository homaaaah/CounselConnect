"""Appointment call authorization and ICE configuration.

The domain rules stay in the appointments service. This service only exposes
the call window, participant-facing labels, and the environment-configured ICE
list. Nothing here is persisted.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AppError
from app.database import get_session
from app.modules.appointments.service import AppointmentsService
from app.modules.calls.schemas import CallConfigResponse, CallIceServer


class CallsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.appointments = AppointmentsService(session)

    def call_config(self, actor, appointment_id):
        context = self.appointments.call_context(actor, appointment_id)
        return CallConfigResponse(
            appointment_id=context.appointment.appointment_id,
            role=context.actor_role,
            peer_role=context.peer_role,
            can_call=context.can_call,
            starts_at=context.starts_at,
            ends_at=context.ends_at,
            safety_deadline_at=context.safety_deadline_at,
            server_time=context.server_time,
            ice_servers=self.ice_servers() if context.can_call else [],
        )

    def authorize_socket(self, actor, appointment_id):
        """Return a callable appointment context or raise a safe AppError."""
        context = self.appointments.call_context(actor, appointment_id)
        if not context.can_call:
            raise AppError(
                "CALL_NOT_AVAILABLE",
                "This appointment is not in a callable window.",
                status_code=403,
            )
        return context

    @staticmethod
    def ice_servers() -> list[CallIceServer]:
        return [
            CallIceServer(
                urls=list(server.urls),
                username=server.username,
                credential=server.credential,
            )
            for server in get_settings().call_ice_servers
        ]


def get_calls_service(session: Session = Depends(get_session)) -> CallsService:
    return CallsService(session)
