"""Standard response/error payload models (docs/API_CONTRACT.md shapes)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ValidationFieldError(BaseModel):
    loc: list[str | int]
    type: str
    message: str


class ValidationDetails(BaseModel):
    fields: list[ValidationFieldError]


class ValidationErrorDetail(BaseModel):
    code: str
    message: str
    details: ValidationDetails


class ValidationErrorResponse(BaseModel):
    error: ValidationErrorDetail
