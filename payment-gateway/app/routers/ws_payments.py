import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.db.database import AsyncSessionLocal
from app.schemas.payment import CrearPagoRequest, WebSocketMessage
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/pagos")
async def ws_pagos(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        raw = await websocket.receive_json()
        try:
            payload = CrearPagoRequest.model_validate(raw)
        except ValidationError as exc:
            await websocket.send_json({"error": "Datos inválidos", "detalle": exc.errors()})
            await websocket.close(code=1008)
            return

        async with AsyncSessionLocal() as db:
            try:
                async def on_event(msg: WebSocketMessage) -> None:
                    await websocket.send_json(msg.model_dump(mode="json"))

                await PaymentService(db).create_payment(payload, on_event=on_event)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        await websocket.close(code=1000)

    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado antes de completar el pago")
