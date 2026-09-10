"""Shared OOP base classes for the module layering (ARCHITECTURE.md):

    router -> service -> repository -> models

- Repository: persistence only (SQLAlchemy queries; no authorization,
  no business rules).
- Service: authorization + business rules + state transitions; the only
  class other modules may import (cross-module via service contracts).
- Router: thin HTTP transport delegating to the service via Depends.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Persistence-only base class. One repository per module."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity

    def get(self, entity_id: Any) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list(self, statement: Select[tuple[ModelT]]) -> list[ModelT]:
        return list(self.session.scalars(statement))

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)


class BaseService(Generic[ModelT]):
    """Authorization + business-rules base class.

    Subclasses receive their module's repository via constructor injection
    (FastAPI Depends wires Session -> Repository -> Service). Authorization
    checks and state-machine transitions live here — never in routers,
    never in repositories.
    """

    repository: BaseRepository[ModelT]

    def __init__(self, repository: BaseRepository[ModelT]) -> None:
        self.repository = repository

    def ensure_found(self, entity: ModelT | None, code: str, message: str) -> ModelT:
        """Return the entity or raise the standard 404 AppError envelope."""
        if entity is None:
            raise AppError(code=code, message=message, status_code=404)
        return entity
