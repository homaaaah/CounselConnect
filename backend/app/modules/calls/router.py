"""Appointment call transport: authorized ICE config + authenticated signaling."""

from __future__ import annotations

import asyncio
import json
from time import monotonic

from fastapi import APIRouter, Depends, Response, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.exceptions import AppError
from app.modules.calls import realtime as call_realtime
from app.modules.calls.schemas import CallConfigResponse
from app.modules.calls.service import CallsService, get_calls_service
from app.shared.dependencies import CurrentUser
from app.shared.realtime import origin_allowed, socket_cookie

router = APIRouter(tags=["calls"])


def _private(response: Response):
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/appointments/{appointment_id}/call",
    response_model=CallConfigResponse,
    dependencies=[Depends(_private)],
)
def call_config(
    appointment_id: int,
    actor: CurrentUser,
    service: CallsService = Depends(get_calls_service),
):
    return service.call_config(actor, appointment_id)


@router.websocket("/appointments/{appointment_id}/call/ws")
async def call_socket(websocket: WebSocket, appointment_id: int):
    if not origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008, reason="Call not authorized")
        return
    raw_credential = socket_cookie(websocket)
    try:
        identity = await asyncio.to_thread(
            call_realtime.authorize_call_socket, raw_credential, appointment_id
        )
    except AppError:
        await websocket.close(code=1008, reason="Call not authorized")
        return

    await websocket.accept()
    peer = await call_realtime.registry.join(appointment_id, identity, websocket)
    settings = get_settings()
    last_revalidated = monotonic()
    receive_task = asyncio.create_task(websocket.receive_text())
    try:
        while True:
            remaining = max(
                0.01,
                call_realtime.SOCKET_REVALIDATE_SECONDS - (monotonic() - last_revalidated),
            )
            done, _ = await asyncio.wait({receive_task}, timeout=remaining)
            raw_message = None
            if receive_task in done:
                try:
                    raw_message = receive_task.result()
                except WebSocketDisconnect:
                    break
                receive_task = asyncio.create_task(websocket.receive_text())

            # Revalidate by wall clock, not by message inactivity, so a client
            # that keeps sending messages cannot outlive its authorization.
            if monotonic() - last_revalidated >= call_realtime.SOCKET_REVALIDATE_SECONDS:
                try:
                    refreshed = await asyncio.to_thread(
                        call_realtime.authorize_call_socket, raw_credential, appointment_id
                    )
                except AppError:
                    await call_realtime.registry.send_terminal(
                        peer, {"type": "call-ended", "reason": "CALL_UNAVAILABLE"}
                    )
                    break
                if refreshed.session_id != identity.session_id:
                    await call_realtime.registry.send_terminal(
                        peer, {"type": "call-ended", "reason": "SESSION_ENDED"}
                    )
                    break
                last_revalidated = monotonic()

            if raw_message is None:
                continue

            too_large = len(raw_message.encode("utf-8")) > settings.call_signal_max_bytes
            if too_large or not call_realtime.registry.allow_message(
                peer, settings.call_signal_messages_per_minute
            ):
                await websocket.close(code=1008, reason="Invalid signaling message")
                break
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.close(code=1008, reason="Invalid signaling message")
                break
            event = call_realtime.validate_signal(message)
            if event is None:
                await websocket.close(code=1008, reason="Invalid signaling message")
                break
            if event["type"] == "ready":
                await call_realtime.registry.mark_ready(appointment_id, peer)
            elif event["type"] == "hangup":
                call_realtime.registry.relay(
                    appointment_id,
                    peer.user_id,
                    {"type": "call-ended", "reason": "PEER_HUNG_UP"},
                )
                break
            else:
                call_realtime.registry.relay(appointment_id, peer.user_id, event)
    except (WebSocketDisconnect, AppError):
        pass
    finally:
        if not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except (asyncio.CancelledError, Exception):
                pass
        await call_realtime.registry.leave(appointment_id, peer)
        try:
            await websocket.close()
        except RuntimeError:
            pass
