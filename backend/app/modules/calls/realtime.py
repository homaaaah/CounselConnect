"""Ephemeral, single-process signaling rooms for appointment calls (ADR-034).

The registry carries SDP/ICE and ephemeral expression-cue events between the
two authorized participants only. It never persists, logs, or replays signaling
payloads. A process restart or multi-worker deployment simply drops rooms;
clients must rejoin.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from threading import RLock
from time import monotonic

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.database import get_engine
from app.modules.auth.service import AuthService
from app.modules.calls.service import CallsService
from app.shared.realtime import SocketIdentity

SOCKET_REVALIDATE_SECONDS = 30
QUEUE_SIZE = 100

EXPRESSION_EVENTS = {"request", "consent", "decline", "unavailable", "result", "stop"}
EXPRESSION_LABELS = {
    "neutral",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgusted",
    "surprised",
}
EXPRESSION_STUDENT_EVENTS = {"consent", "decline", "unavailable", "result"}


@dataclass(eq=False)
class CallPeer:
    appointment_id: int
    user_id: int
    role_code: str
    websocket: WebSocket
    session_id: int
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop | None = None
    writer: asyncio.Task | None = None
    ready: bool = False
    window_started: float = 0.0
    window_count: int = 0


def authorize_call_socket(raw_credential: str | None, appointment_id: int) -> SocketIdentity:
    """Authenticate and reauthorize the appointment call in a short-lived session."""
    with Session(get_engine(), expire_on_commit=False) as session:
        actor, user_session = AuthService(session).authenticate_request(
            raw_credential, None, is_safe_method=True, record_activity=False
        )
        CallsService(session).authorize_socket(actor, appointment_id)
        return SocketIdentity(
            actor.user_id,
            actor.role_code,
            actor.account_status,
            user_session.session_id,
        )


def validate_signal(message) -> dict | None:
    """Allowlist the client signaling shape; return None for anything invalid."""
    if not isinstance(message, dict):
        return None
    kind = message.get("type")
    if kind in ("ready", "hangup"):
        return {"type": kind}
    if kind in ("offer", "answer"):
        sdp = message.get("sdp")
        if not isinstance(sdp, str) or not sdp.strip():
            return None
        return {"type": kind, "sdp": sdp}
    if kind == "ice-candidate":
        candidate = message.get("candidate")
        if candidate is not None and not isinstance(candidate, dict):
            return None
        return {"type": kind, "candidate": candidate}
    if kind == "expression":
        return _validate_expression(message)
    return None


def _validate_expression(message: dict) -> dict | None:
    """Validate one ephemeral expression-cue message; never logs its payload."""
    event = message.get("event")
    if not isinstance(event, str) or event not in EXPRESSION_EVENTS:
        return None
    if event == "stop":
        return {"type": "expression", "event": "stop"}
    request_id = message.get("id")
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
        return None
    if event in EXPRESSION_STUDENT_EVENTS - {"result"}:
        return {"type": "expression", "event": event, "id": request_id}
    if event == "result":
        label = message.get("label")
        confidence = message.get("confidence")
        if not isinstance(label, str) or label not in EXPRESSION_LABELS:
            return None
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return None
        # Range-check before float conversion: an oversized JSON integer must
        # not raise OverflowError and escape the 1008 validation path.
        if not 0 <= confidence <= 1:
            return None
        value = float(confidence)
        if not math.isfinite(value):
            return None
        return {
            "type": "expression",
            "event": "result",
            "id": request_id,
            "label": label,
            "confidence": round(value, 3),
        }
    return {"type": "expression", "event": event, "id": request_id}


def expression_allowed(role_code: str, event: str) -> bool:
    """Enforce the expression role matrix on the server, not in the browser."""
    if event == "request":
        return role_code == "COUNSELOR"
    if event in EXPRESSION_STUDENT_EVENTS:
        return role_code == "STUDENT"
    if event == "stop":
        return role_code in ("STUDENT", "COUNSELOR")
    return False


class CallRoomRegistry:
    """One call room per appointment; at most one live socket per participant."""

    def __init__(self) -> None:
        self._rooms: dict[int, dict[int, CallPeer]] = {}
        self._guard = RLock()

    async def join(self, appointment_id: int, identity: SocketIdentity, websocket: WebSocket) -> CallPeer:
        peer = CallPeer(
            appointment_id=appointment_id,
            user_id=identity.user_id,
            role_code=identity.role_code,
            websocket=websocket,
            session_id=identity.session_id,
            queue=asyncio.Queue(maxsize=QUEUE_SIZE),
            loop=asyncio.get_running_loop(),
        )
        peer.writer = asyncio.create_task(self._writer(peer))
        replaced = None
        other = None
        with self._guard:
            room = self._rooms.setdefault(appointment_id, {})
            replaced = room.get(identity.user_id)
            other = next((item for user_id, item in room.items() if user_id != identity.user_id), None)
            room[identity.user_id] = peer
            if replaced is not None and other is not None:
                # A duplicate window takes over the call; end the paired call
                # for the other participant rather than leaving a stale peer.
                room.pop(other.user_id, None)

        if replaced is not None:
            await self.send_terminal(replaced, {"type": "call-ended", "reason": "REPLACED"})
            await self._close(replaced)
            if other is not None:
                await self.send_terminal(other, {"type": "call-ended", "reason": "REPLACED"})
                await self._close(other)
            self.send_to(peer, {
                "type": "room-state",
                "peer_present": False,
                "initiator": False,
                "peer_role": None,
            })
        else:
            self.send_to(peer, {
                "type": "room-state",
                "peer_present": other is not None,
                "initiator": False,
                "peer_role": other.role_code if other is not None else None,
            })
        return peer

    async def mark_ready(self, appointment_id: int, peer: CallPeer) -> None:
        with self._guard:
            room = self._rooms.get(appointment_id) or {}
            if room.get(peer.user_id) is not peer or peer.ready:
                return
            peer.ready = True
            other = next((item for user_id, item in room.items() if user_id != peer.user_id), None)
        if other is not None and other.ready:
            # The second participant to become ready initiates the offer.
            self.send_to(peer, {
                "type": "room-state",
                "peer_present": True,
                "initiator": True,
                "peer_role": other.role_code,
            })
            self.send_to(other, {
                "type": "peer-joined",
                "initiator": False,
                "peer_role": peer.role_code,
            })

    def relay(self, appointment_id: int, sender_user_id: int, event: dict) -> None:
        with self._guard:
            room = self._rooms.get(appointment_id) or {}
            other = next((item for user_id, item in room.items() if user_id != sender_user_id), None)
        if other is not None:
            self.send_to(other, event)

    async def leave(self, appointment_id: int, peer: CallPeer) -> None:
        removed = False
        other = None
        with self._guard:
            room = self._rooms.get(appointment_id)
            if room is not None and room.get(peer.user_id) is peer:
                room.pop(peer.user_id, None)
                removed = True
                other = next((item for user_id, item in room.items() if user_id != peer.user_id), None)
                if not room:
                    self._rooms.pop(appointment_id, None)
        if removed and other is not None:
            # A disconnect can cancel this task at the next await. Notify the
            # remaining peer before awaiting cleanup so peer-left is not lost.
            self.send_to(other, {"type": "peer-left"})
        await self._close(peer)

    def send_to(self, peer: CallPeer, event: dict) -> None:
        def deliver():
            try:
                peer.queue.put_nowait(event)
            except asyncio.QueueFull:
                asyncio.create_task(self.leave(peer.appointment_id, peer))
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if peer.loop is not None and current is not peer.loop:
            if not peer.loop.is_closed():
                peer.loop.call_soon_threadsafe(deliver)
        else:
            deliver()

    async def send_terminal(self, peer: CallPeer, event: dict) -> None:
        """Stop the writer, then send one final event without concurrent sends."""
        if peer.loop is not None and asyncio.get_running_loop() is not peer.loop:
            if not peer.loop.is_closed():
                await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(self.send_terminal(peer, event), peer.loop))
            return
        writer = peer.writer
        peer.writer = None
        if writer is not None and not writer.done():
            writer.cancel()
            try:
                await writer
            except (asyncio.CancelledError, Exception):
                pass
        try:
            await peer.websocket.send_json(event)
        except Exception:
            pass

    @staticmethod
    def allow_message(peer: CallPeer, limit: int) -> bool:
        now = monotonic()
        if now - peer.window_started >= 60:
            peer.window_started = now
            peer.window_count = 0
        peer.window_count += 1
        return peer.window_count <= limit

    async def _writer(self, peer: CallPeer) -> None:
        try:
            while True:
                event = await peer.queue.get()
                await asyncio.wait_for(peer.websocket.send_json(event), timeout=5)
        except (asyncio.CancelledError, Exception):
            if peer.writer is not None:
                peer.writer = None
                await self.leave(peer.appointment_id, peer)

    @staticmethod
    async def _close(peer: CallPeer, *, code: int = 1008, reason: str = "Call ended") -> None:
        if peer.loop is not None and asyncio.get_running_loop() is not peer.loop:
            if not peer.loop.is_closed():
                await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(CallRoomRegistry._close(peer, code=code, reason=reason), peer.loop))
            return
        writer = peer.writer
        peer.writer = None
        if writer is not None:
            writer.cancel()
        try:
            await peer.websocket.close(code=code, reason=reason)
        except Exception:
            pass


registry = CallRoomRegistry()
