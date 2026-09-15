"""assistant repository (persistence only).

The assistant owns NO tables. It reads through the CONTENT and
WELLNESS_RESOURCES module services (cross-module service contracts per
ARCHITECTURE.md), never their repositories directly.
"""

from __future__ import annotations


class AssistantRepository:
    """No owned tables; kept for layering symmetry.

    # TODO: Wire reads through content/wellness services when implemented
    # (deterministic retrieval per ADR-027; no provider integration in v1).
    """

    def __init__(self, session) -> None:  # noqa: ANN001 - SQLAlchemy Session
        self.session = session
