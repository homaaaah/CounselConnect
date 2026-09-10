"""operations Pydantic contracts.

# TODO: Define concrete DTOs when operations workflows are implemented
# (authorization context pending ADR-P01).
"""

from __future__ import annotations

from pydantic import BaseModel


class OperationsDashboardResponse(BaseModel):
    """Placeholder for the counselor dashboard aggregate."""

    pass
