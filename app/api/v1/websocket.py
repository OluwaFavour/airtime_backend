import json
from typing import Annotated, Dict
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from app.services.websocket_manager import ConnectionManager, get_websocket_manager


router = APIRouter()


@router.websocket("/wallet")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: Annotated[ConnectionManager, Depends(get_websocket_manager)],
):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        parsed_data: Dict[str, str] = json.loads(data)
        tx_ref = parsed_data.get("tx_ref")

        if not tx_ref:
            await websocket.close(
                code=status.WS_1003_UNSUPPORTED_DATA, reason="Missing tx_ref"
            )
            return

        # Register the connection with the manager
        manager.connect(tx_ref, websocket)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(tx_ref, websocket)
