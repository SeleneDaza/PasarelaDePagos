import logging

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
from app.schemas.payment import CrearPagoRequest
from app.services.card_client import CardClient, CardServiceError


class PaymentService:
    """Orquesta el flujo de crear pago: valida empresa, llama tarjeta, persiste."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.card_client = CardClient()

    async def create_payment(self, request: CrearPagoRequest) -> Transaccion:
        self._log_payment_start(request)
        company = await self._get_active_company(request.empresa_id)
        logger.info("Empresa validada: %s", company.nombre, extra={"empresa_id": str(request.empresa_id)})
        try:
            card_is_valid = await self._verify_card(request)
        except CardServiceError as exc:
            return await self._register_failed_transaction(request, exc)
        transaction_status, liquidation_status = self._resolve_status(card_is_valid)
        return await self._save_transaction(request, transaction_status, liquidation_status)

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

    async def _register_failed_transaction(
        self,
        request: CrearPagoRequest,
        error: CardServiceError,
    ) -> Transaccion:
        logger.warning(
            "Fallo técnico al verificar tarjeta: %s",
            error,
            extra={"empresa_id": str(request.empresa_id)},
        )
        transaction = self._build_transaction(
            request=request,
            transaction_status=EstadoTransaccion.fallido,
            liquidation_status=None,
        )
        self.db.add(transaction)
        await self.db.flush()
        logger.info("Transacción registrada con estado=fallido, id=%s", transaction.id)
        return transaction

    def _resolve_status(
        self,
        card_is_valid: bool,
    ) -> tuple[EstadoTransaccion, EstadoLiquidacion | None]:
        if card_is_valid:
            return EstadoTransaccion.aprobado, EstadoLiquidacion.no_liquidado
        return EstadoTransaccion.rechazado, None

    async def _save_transaction(
        self,
        request: CrearPagoRequest,
        transaction_status: EstadoTransaccion,
        liquidation_status: EstadoLiquidacion | None,
    ) -> Transaccion:
        transaction = self._build_transaction(
            request=request,
            transaction_status=transaction_status,
            liquidation_status=liquidation_status,
        )
        self.db.add(transaction)
        await self.db.flush()
        logger.info(
            "Transacción registrada",
            extra={"transaccion_id": str(transaction.id), "estado": transaction_status.value},
        )
        return transaction

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
