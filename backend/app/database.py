"""Sync SQLAlchemy engine/session for PyMySQL (ADR-002).

- One engine per process; sessions scoped per request via get_session.
- Connection time zone forced to UTC (timestamps are stored/read as UTC).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal: sessionmaker | None = None


def _build_engine():
    url = get_settings().database_url
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"init_command": "SET time_zone = '+00:00'"},
    )


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request; commit on success."""
    get_engine()
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
