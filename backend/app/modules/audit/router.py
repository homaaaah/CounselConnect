"""audit router (thin HTTP transport).

Reading audit activity is COUNSELOR-only; authorization is enforced in the
service layer (not implemented pending ADR-P01).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.audit.service import AuditService, get_audit_service

router = APIRouter(prefix="/audit-events", tags=["audit"])
