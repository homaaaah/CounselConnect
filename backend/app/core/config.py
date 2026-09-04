"""Settings re-export.

The single Settings definition lives in app.config (imported by Alembic's
env.py without pulling in FastAPI). This module is the canonical import path
for application code: `from app.core.config import get_settings`.
"""

from __future__ import annotations

from app.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
