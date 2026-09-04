"""sos service: authorization + business rules.

Core rules (docs/SOS_TRIAGE.md, ARCHITECTURE.md):
- Five approved questions, evaluated by APPROVED RULE-BASED conditions only
  (no AI scoring; the optional Observed Expression Cue NEVER affects SOS).
- OPEN -> RESPONDED -> CLOSED lifecycle; counselor claim/respond/close.
- Emergency-contact fallback when counselor support is unavailable under
  the final approved rule.

# TODO: SOS instrument, thresholds, and answer retention are pending ADR-P03.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.modules.bases import BaseService
from app.modules.sos.models import SosCase
from app.modules.sos.repository import SosRepository


class SosService(BaseService[SosCase]):
    """SOS triage business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(SosRepository(session))


def get_sos_service(session: Session = Depends(get_session)) -> SosService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return SosService(session)
