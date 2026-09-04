"""operations repository (persistence only).

The operations module owns NO tables. Cross-module access goes through the
owning module's service (ARCHITECTURE.md), so this repository is a
placeholder for layering symmetry only.

# TODO: Implement after ADR-P01 (authorization context pending).
"""

from __future__ import annotations


class OperationsRepository:
    """No owned tables; placeholder for layering symmetry."""

    def __init__(self, session) -> None:  # noqa: ANN001 - SQLAlchemy Session
        self.session = session
