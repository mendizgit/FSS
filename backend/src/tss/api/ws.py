"""GET /ws: pushes hub events to the browser (Arch §10). Read-only; client messages are ignored."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    hub = websocket.app.state.hub
    await websocket.accept()
    queue = hub.subscribe()
    receiver = asyncio.create_task(websocket.receive_text())  # only to notice disconnects
    try:
        while True:
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:
                getter.cancel()
                receiver.result()  # raises WebSocketDisconnect when the client left
                receiver = asyncio.create_task(websocket.receive_text())
                continue
            await websocket.send_text(getter.result())
    except WebSocketDisconnect:
        pass
    finally:
        receiver.cancel()
        hub.unsubscribe(queue)
