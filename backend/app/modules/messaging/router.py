"""messaging router (thin HTTP transport).

Nested resource per NAMING_CONVENTIONS.md:
/conversations/{conversation_id}/messages
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Response, WebSocket, WebSocketDisconnect

from app.modules.messaging.schemas import ConversationResponse, MessageCreateRequest, MessageHistoryResponse, MessageResponse
from app.modules.messaging.service import MessagingService, get_messaging_service
from app.shared.dependencies import CurrentUser
from app.core.exceptions import AppError
from app.modules.messaging.realtime import authorize_conversation_socket, registry, websocket_identity

router = APIRouter(prefix="/conversations", tags=["messaging"])


def _private(response: Response):
    response.headers["Cache-Control"] = "no-store"


@router.get("/{conversation_id}", response_model=ConversationResponse, dependencies=[Depends(_private)])
def conversation_detail(conversation_id: int, actor: CurrentUser, service: MessagingService = Depends(get_messaging_service)):
    return service.conversation_detail(actor, conversation_id)


@router.get("/{conversation_id}/messages", response_model=MessageHistoryResponse, dependencies=[Depends(_private)])
def message_history(
    conversation_id: int,
    actor: CurrentUser,
    before_sequence: int | None = Query(None, ge=1),
    after_sequence: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: MessagingService = Depends(get_messaging_service),
):
    return service.history(actor, conversation_id, before_sequence=before_sequence, after_sequence=after_sequence, limit=limit)


@router.post("/{conversation_id}/messages", response_model=MessageResponse, dependencies=[Depends(_private)])
def send_message(
    conversation_id: int,
    data: MessageCreateRequest,
    actor: CurrentUser,
    service: MessagingService = Depends(get_messaging_service),
):
    message = service.send_message(actor, conversation_id, data)
    # Delivery may only happen after the durable commit. The request dependency
    # will harmlessly commit again during teardown.
    service.repository.session.commit()
    registry.publish_from_thread(
        f"conversation:{conversation_id}",
        {"event": "message_created", "message": MessageResponse.model_validate(message, from_attributes=True).model_dump(mode="json")},
    )
    return message


@router.websocket("/{conversation_id}/ws")
async def conversation_socket(websocket: WebSocket, conversation_id: int):
    try:
        identity = await websocket_identity(websocket, conversation_id=conversation_id)
    except AppError:
        await websocket.close(code=1008, reason="Connection not authorized")
        return
    await websocket.accept()
    channel = f"conversation:{conversation_id}"
    connection = await registry.add(channel, websocket, identity.session_id)
    raw = websocket.cookies.get("counselconnect_session")
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                refreshed = await asyncio.to_thread(authorize_conversation_socket, raw, conversation_id)
                if refreshed.session_id != identity.session_id:
                    break
    except (WebSocketDisconnect, AppError):
        pass
    finally:
        await registry.remove(channel, connection)
        try:
            await websocket.close()
        except RuntimeError:
            pass
