"""Shared pytest fixtures.

The project targets MySQL 8.4; tests that need a database should use a
dedicated test database configured via COUNSELCONNECT_* env vars.

# TODO: Add application + DB fixtures when the first real tests arrive
# (do not invent feature tests before implementation exists).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def app():
    """Fresh application per test (no DB connection required for health)."""
    return create_app()


@pytest.fixture()
def client(app):
    """TestClient bound to the fresh app."""
    return TestClient(app)
