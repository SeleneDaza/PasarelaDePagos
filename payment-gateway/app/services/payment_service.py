import logging
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.models import (
    Empresa,
    EstadoLiquidacion,
    EstadoTransaccion,
    Transaccion,
)
from app.schemas.payment import CrearPagoRequest, WebSocketMessage, WebSocketPhase
from app.services.card_client import CardClient, CardServiceError


class PaymentService:
    """Orquesta el flujo de crear pago: valida empresa, llama tarjeta, persiste."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.card_client = CardClient()

    async def create_payment(
        self,
        request: CrearPagoRequest,
        on_event: Callable[[WebSocketMessage], Awaitable[None]] | None = None,
    ) -> Transaccion:
        self._log_payment_start(request)
        company = await self._get_active_company(request.empresa_id)
        logger.info("Empresa validada: %s", company.nombre, extra={"empresa_id": str(request.empresa_id)})

        transaction = self._build_transaction(
            request=request,
            transaction_status=EstadoTransaccion.aprobado,
            liquidation_status=None,
        )
        self.db.add(transaction)
        await self.db.flush()
        if on_event:
            await on_event(WebSocketMessage(
                fase=WebSocketPhase.transaccion_creada,
                mensaje="Transacción creada",
                detalle=f"Transacción registrada con id={transaction.id}",
            ))

        if on_event:
            await on_event(WebSocketMessage(
                fase=WebSocketPhase.verificando_tarjeta,
                mensaje="Verificando tarjeta",
                detalle=f"Consultando servicio {request.tipo_tarjeta.value} para tarjeta terminada en {request.numero_tarjeta[-4:]}",
            ))
        try:
            card_is_valid = await self._verify_card(request)
        except CardServiceError as exc:
            transaction.estado_transaccion = EstadoTransaccion.fallido
            transaction.estado_liquidacion = None
            await self.db.flush()
            logger.warning(
                "Fallo técnico al verificar tarjeta: %s",
                exc,
                extra={"empresa_id": str(request.empresa_id)},
            )
            if on_event:
                await on_event(WebSocketMessage(
                    fase=WebSocketPhase.respuesta_tarjeta,
                    mensaje="Error en servicio de tarjeta",
                    detalle=f"El servicio de tarjeta devolvió un error técnico: {exc}",
                ))
                await on_event(WebSocketMessage(
                    fase=WebSocketPhase.resultado_final,
                    mensaje="Pago fallido",
                    detalle="La transacción quedó en estado fallido por error técnico en la verificación.",
                    estado_transaccion=EstadoTransaccion.fallido,
                ))
            logger.info("Transacción registrada con estado=fallido, id=%s", transaction.id)
            return transaction

        if card_is_valid:
            detalle_respuesta = "La tarjeta fue verificada y aprobada por el servicio."
        else:
            detalle_respuesta = "La tarjeta fue rechazada por el servicio de verificación."
        if on_event:
            await on_event(WebSocketMessage(
                fase=WebSocketPhase.respuesta_tarjeta,
                mensaje="Respuesta del servicio de tarjeta recibida",
                detalle=detalle_respuesta,
            ))

        transaction_status, liquidation_status = self._resolve_status(card_is_valid)
        transaction.estado_transaccion = transaction_status
        transaction.estado_liquidacion = liquidation_status
        await self.db.flush()
        logger.info(
            "Transacción registrada",
            extra={"transaccion_id": str(transaction.id), "estado": transaction_status.value},
        )
        if on_event:
            await on_event(WebSocketMessage(
                fase=WebSocketPhase.resultado_final,
                mensaje="Resultado final",
                detalle=f"La transacción finalizó con estado '{transaction_status.value}'.",
                estado_transaccion=transaction_status,
            ))
        return transaction

    def _log_payment_start(self, request: CrearPagoRequest) -> None:
        logger.info(
            "Iniciando pago",
            extra={
                "empresa_id": str(request.empresa_id),
                "monto": str(request.monto),
                "tipo_tarjeta": request.tipo_tarjeta,
            },
        )

    async def _verify_card(self, request: CrearPagoRequest) -> bool:
        return await self.card_client.verify_card(
            card_type=request.tipo_tarjeta,
            card_number=request.numero_tarjeta,
            cvv=request.cvv,
            expiration_date=request.fecha_expiracion,
        )

    def _resolve_status(
        self,
        card_is_valid: bool,
    ) -> tuple[EstadoTransaccion, EstadoLiquidacion | None]:
        if card_is_valid:
            return EstadoTransaccion.aprobado, EstadoLiquidacion.no_liquidado
        return EstadoTransaccion.rechazado, None

    # ---------- Helpers privados ----------

    async def _get_active_company(self, company_id) -> Empresa:
        result = await self.db.execute(
            select(Empresa).where(Empresa.id == company_id)
        )
        company = result.scalar_one_or_none()
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
        if not company.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no autorizada para cobrar.",
            )
        return company

    def _build_transaction(
        self,
        request: CrearPagoRequest,
        transaction_status: EstadoTransaccion,
        liquidation_status: EstadoLiquidacion | None,
    ) -> Transaccion:
        # cliente_id es el ID que el cliente tiene en la BD de su tarjeta.
        # Por ahora usamos los últimos 4 dígitos como placeholder hasta que los
        # serverless devuelvan el ID real del cliente.
        return Transaccion(
            empresa_id=request.empresa_id,
            monto=request.monto,
            tipo_tarjeta=request.tipo_tarjeta,
            cliente_id=request.numero_tarjeta[-4:],
            estado_transaccion=transaction_status,
            estado_liquidacion=liquidation_status,
        )
