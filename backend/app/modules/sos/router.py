"""sos router (thin HTTP transport).

Action endpoint per NAMING_CONVENTIONS.md:
POST /sos-cases/{sos_case_id}/close
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.sos.service import SosService, get_sos_service

router = APIRouter(prefix="/sos-cases", tags=["sos"])
