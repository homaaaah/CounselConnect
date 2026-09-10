"""assistant Pydantic contracts (docs/API_CONTRACT.md shapes).

# Request/response shapes are stable under ADR-027 (deterministic retrieval).
"""

from __future__ import annotations

from pydantic import BaseModel


class AssistantQueryRequest(BaseModel):
    query: str


class AssistantResponse(BaseModel):
    """Bounded response: navigation, FAQ, resource recommendation, or limitation."""

    response_type: str  # NAVIGATION | FAQ | RESOURCE_RECOMMENDATION | LIMITATION
    body: str
