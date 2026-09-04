"""sos repository (persistence only)."""

from __future__ import annotations

from app.modules.bases import BaseRepository
from app.modules.sos.models import SosCase, SosResponse


class SosRepository(BaseRepository[SosCase]):
    """Owns all SOS-domain SQLAlchemy queries."""

    model = SosCase

    def list_responses_for_case(self, sos_case_id: int) -> list[SosResponse]:
        return list(
            self.session.query(SosResponse).filter(SosResponse.sos_case_id == sos_case_id)
        )
