"""Aggregates every module's router under /api/v1 (docs/API_CONTRACT.md).

Modules stay separate by domain but are mounted into this ONE application.
Cross-module access goes through service contracts (ARCHITECTURE.md), never
by importing another module's repository or models directly.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.accounts.router import router as accounts_router
from app.modules.appointments.router import router as appointments_router
from app.modules.assistant.router import router as assistant_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.content.router import router as content_router
from app.modules.enrollment_verification.router import router as enrollment_verification_router
from app.modules.messaging.router import router as messaging_router
from app.modules.operations.router import router as operations_router
from app.modules.sos.router import router as sos_router
from app.modules.wellness_resources.router import router as wellness_resources_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(accounts_router)
api_router.include_router(enrollment_verification_router)
api_router.include_router(appointments_router)
api_router.include_router(messaging_router)
api_router.include_router(sos_router)
api_router.include_router(wellness_resources_router)
api_router.include_router(assistant_router)
api_router.include_router(content_router)
api_router.include_router(operations_router)
api_router.include_router(audit_router)


@api_router.get("/health", tags=["health"], summary="Liveness probe")
def health() -> dict[str, str]:
    """Minimal health check; no data access, no auth required."""
    return {"status": "ok"}
