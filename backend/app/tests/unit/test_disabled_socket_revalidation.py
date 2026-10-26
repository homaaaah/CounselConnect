"""Busy notification sockets still reach their wall-clock session check."""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppError


@pytest.mark.parametrize("domain", ["messaging", "appointments"])
def test_busy_socket_revalidates_and_closes(domain, monkeypatch):
    module = importlib.import_module(f"app.modules.{domain}.router")
    identity = SimpleNamespace(user_id=1, session_id=2, account_status="ACTIVE", role_code="STUDENT")
    websocket = SimpleNamespace(accept=AsyncMock(), close=AsyncMock(), receive_text=AsyncMock(return_value="ping"),
                                cookies={"counselconnect_session": "opaque"})
    monkeypatch.setattr(module, "websocket_identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(module, "registry", SimpleNamespace(add=AsyncMock(return_value=object()), remove=AsyncMock()))
    clock = iter([0, 1, 31, 31])
    monkeypatch.setattr(module, "monotonic", lambda: next(clock))
    authorize = Mock(side_effect=AppError("ACCOUNT_DEACTIVATED", "Account is deactivated.", status_code=403))
    monkeypatch.setattr(module, "authorize_conversation_socket" if domain == "messaging" else "authenticate_socket", authorize)
    if domain == "messaging":
        asyncio.run(module.conversation_socket(websocket, 1))
    else:
        asyncio.run(module.appointment_session_events(websocket))
    authorize.assert_called_once()
    websocket.close.assert_awaited_once()
    assert websocket.receive_text.await_count == 1
