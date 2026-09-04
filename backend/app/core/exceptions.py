"""Shared error model and FastAPI exception handlers.

Error envelope per NAMING_CONVENTIONS.md / docs/API_CONTRACT.md:

    {"error": {"code": "SLOT_UNAVAILABLE", "message": "...", "details": {}}}

Codes are stable SCREAMING_SNAKE_CASE; messages are human-readable; details
never contain secrets.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base for all handled API errors carrying a stable machine code."""

    status_code: int = status.HTTP_409_CONFLICT

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install_error_handlers(app: FastAPI) -> None:
    """Register the project-standard error envelope handlers."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(exc.to_payload()))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(
                _envelope("VALIDATION_ERROR", "Request validation failed.", exc.errors())
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, __: Exception) -> JSONResponse:
        # Safe generic response: never leak internals or stack traces.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(_envelope("INTERNAL_ERROR", "An unexpected error occurred.")),
        )
