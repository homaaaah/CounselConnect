"""sos Pydantic contracts (docs/API_CONTRACT.md shapes).

Action endpoint per NAMING_CONVENTIONS.md:
POST /sos-cases/{sos_case_id}/close
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SosCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sos_case_id: int
    student_user_id: int
    assigned_counselor_user_id: int | None
    conversation_id: int | None
    instrument_version: str
    urgency_result_code: str | None
    status: Literal["OPEN", "RESPONDED", "CLOSED"]
    submitted_at: datetime
    responded_at: datetime | None
    closed_at: datetime | None


class SosAnswerSubmitRequest(BaseModel):
    """Structure placeholder; exact questions are pending ADR-P03."""

    question_key: str
    answer_value: str
