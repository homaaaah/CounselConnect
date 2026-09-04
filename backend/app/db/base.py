"""DeclarativeBase with stable naming conventions for Alembic autogeneration.

Table/column/index names come from the approved v4 SQL
(CounselConnect_Initial_Database_v4.sql) — models must not rename them.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "idx_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "chk_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def import_all_models() -> None:
    """Idempotently import every module's models for metadata registration.

    Called by Alembic's env.py (and any code needing complete metadata).
    """
    from app.modules.accounts import models  # noqa: F401
    from app.modules.appointments import models  # noqa: F401
    from app.modules.audit import models  # noqa: F401
    from app.modules.content import models  # noqa: F401
    from app.modules.enrollment_verification import models  # noqa: F401
    from app.modules.messaging import models  # noqa: F401
    from app.modules.sos import models  # noqa: F401
    from app.modules.wellness_resources import models  # noqa: F401
