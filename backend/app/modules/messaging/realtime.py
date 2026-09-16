"""Single-process, session-bound WebSocket delivery for the v1 prototype."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import RLock

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AppError
from app.database import get_engine
from app.modules.auth.service import AuthService, SESSION_COOKIE
from app.modules.messaging.service import MessagingService


@dataclass(frozen=True)
class SocketIdentity:
    user_id: int
    role_code: str
    account_status: str
    session_id: int


@dataclass(eq=False)
class _Connection:
    websocket: WebSocket
    session_id: int
    queue: asyncio.Queue
    writer: asyncio.Task | None = None


class ConnectionRegistry:
    """Bounded delivery queues; intentionally local to one backend process."""

    def __init__(self) -> None:
        self._channels: dict[str, set[_Connection]] = {}
        self._guard = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def add(self, channel: str, websocket: WebSocket, session_id: int) -> _Connection:
        connection = _Connection(websocket, session_id, asyncio.Queue(maxsize=100))
        self._loop = asyncio.get_running_loop()
        connection.writer = asyncio.create_task(self._writer(connection))
        with self._guard:
            self._channels.setdefault(channel, set()).add(connection)
        return connection

    async def remove(self, channel: str, connection: _Connection) -> None:
        with self._guard:
            members = self._channels.get(channel)
            if members is not None:
                members.discard(connection)
                if not members:
                    self._channels.pop(channel, None)
        if connection.writer is not None:
            connection.writer.cancel()

    def has_subscribers(self, channel: str) -> bool:
        with self._guard:
            return bool(self._channels.get(channel))

    async def publish(self, channel: str, event: dict) -> int:
        with self._guard:
            members = list(self._channels.get(channel, ()))
        accepted = 0
        for connection in members:
            try:
                connection.queue.put_nowait(event)
                accepted += 1
            except asyncio.QueueFull:
                await connection.websocket.close(code=1013, reason="Client is not keeping up")
        return accepted

    def publish_from_thread(self, channel: str, event: dict):
        loop = self._loop
        if loop is None or loop.is_closed():
            return None
        return asyncio.run_coroutine_threadsafe(self.publish(channel, event), loop)

    @staticmethod
    async def _writer(connection: _Connection) -> None:
        try:
            while True:
                event = await connection.queue.get()
                await asyncio.wait_for(connection.websocket.send_json(event), timeout=5)
        except (asyncio.CancelledError, Exception):
            return


registry = ConnectionRegistry()


def _origin_allowed(origin: str | None) -> bool:
    return bool(origin and origin in get_settings().cors_origins)


def authenticate_socket(raw_credential: str | None) -> SocketIdentity:
    with Session(get_engine(), expire_on_commit=False) as session:
        actor, user_session = AuthService(session).authenticate_request(
            raw_credential, None, is_safe_method=True, record_activity=False
        )
        return SocketIdentity(
            actor.user_id,
            actor.role_code,
            actor.account_status,
            user_session.session_id,
        )


def authorize_conversation_socket(raw_credential: str | None, conversation_id: int) -> SocketIdentity:
    with Session(get_engine(), expire_on_commit=False) as session:
        actor, user_session = AuthService(session).authenticate_request(
            raw_credential, None, is_safe_method=True, record_activity=False
        )
        MessagingService(session).conversation_detail(actor, conversation_id)
        return SocketIdentity(actor.user_id, actor.role_code, actor.account_status, user_session.session_id)


async def websocket_identity(websocket: WebSocket, *, conversation_id: int | None = None) -> SocketIdentity:
    if not _origin_allowed(websocket.headers.get("origin")):
        raise AppError("WEBSOCKET_ORIGIN_DENIED", "The connection origin is not allowed.", status_code=403)
    raw = websocket.cookies.get(SESSION_COOKIE)
    if conversation_id is None:
        return await asyncio.to_thread(authenticate_socket, raw)
    return await asyncio.to_thread(authorize_conversation_socket, raw, conversation_id)
