import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.structured_logger import (
    LogEvent,
    LogLevel,
    LogStatus,
    build_ws_message,
    logError,
    logInfo,
)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/boletos")
async def ticket_websocket(websocket: WebSocket):
    session_id = str(uuid.uuid4())
    client_ip = websocket.client.host if websocket.client else ""
    await websocket.accept()

    logInfo(
        LogEvent.WS_CONNECTED,
        module=__name__,
        message="WebSocket connection established",
        session_id=session_id,
        client_ip=client_ip,
        status=LogStatus.CONNECTED,
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                logError(
                    LogEvent.WS_MESSAGE_RECEIVED,
                    module=__name__,
                    message="Invalid WebSocket message",
                    session_id=session_id,
                    client_ip=client_ip,
                    error_code="WS_INVALID_JSON",
                    technical_detail=str(exc),
                    functional_detail="El mensaje recibido no tiene formato JSON válido",
                )
                continue

            transaction_id = str(data.get("transactionId", ""))
            msg_type = str(data.get("type", "UNKNOWN"))

            logInfo(
                LogEvent.WS_MESSAGE_RECEIVED,
                module=__name__,
                message=f"Message received: type={msg_type}",
                session_id=session_id,
                client_ip=client_ip,
                transaction_id=transaction_id,
                status=LogStatus.DELIVERED,
            )

            ack = build_ws_message(
                message_type="ACK",
                level=LogLevel.INFO,
                source="payment-gateway",
                transaction_id=transaction_id,
                session_id=session_id,
                status=LogStatus.DELIVERED,
            )
            await websocket.send_text(json.dumps(ack))

            logInfo(
                LogEvent.WS_MESSAGE_SENT,
                module=__name__,
                message="ACK sent to client",
                session_id=session_id,
                client_ip=client_ip,
                transaction_id=transaction_id,
                status=LogStatus.SENT,
            )

    except WebSocketDisconnect:
        logInfo(
            LogEvent.WS_CONNECTED,
            module=__name__,
            message="WebSocket connection closed",
            session_id=session_id,
            client_ip=client_ip,
            status=LogStatus.DISCONNECTED,
        )
