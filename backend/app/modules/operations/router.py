"""operations router (thin HTTP transport)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.operations.service import OperationsService, get_operations_service

router = APIRouter(prefix="/operations", tags=["operations"])
