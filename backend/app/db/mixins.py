"""Shared ORM mixin: UTC created_at/updated_at mirroring the v4 DDL defaults."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# MySQL DATETIME(6) via dialect type; generic DateTime elsewhere.
DATETIME6 = DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")
TS_DEFAULT = text("CURRENT_TIMESTAMP(6)")


class TimestampMixin:
    """created_at/updated_at stored as UTC DATETIME(6)."""

    created_at: Mapped[datetime] = mapped_column(
        DATETIME6, nullable=False, server_default=TS_DEFAULT, insert_default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME6,
        nullable=False,
        server_default=TS_DEFAULT,
        insert_default=utcnow,
        onupdate=utcnow,
    )
