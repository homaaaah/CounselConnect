"""API contract test: health endpoint (no auth, no DB)."""

from __future__ import annotations


def test_health_endpoint(client):
    """GET /api/v1/health returns ok without auth or DB access."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
