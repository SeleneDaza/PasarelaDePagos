import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Empresa,
    EstadoLiquidacion,
    EstadoTransaccion,
    Transaccion,
)
from app.schemas.payment import CrearPagoRequest
from app.services.card_client import CardClient, CardServiceError
from app.structured_logger import (
    LogEvent,
    LogStatus,
    elapsed_ms,
    logError,
    logInfo,
    logSuccess,
)

_MODULE = __name__


class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.card_client = CardClient()

    async def create_payment(self, request: CrearPagoRequest) -> Transaccion:
        transaction_id = str(uuid.uuid4())
        start = time.monotonic()

        logInfo(
            LogEvent.PAYMENT_REQUEST_SENT,
            module=_MODULE,
            message="Payment request received",
            transaction_id=transaction_id,
            payment_provider=request.tipo_tarjeta.value,
            status=LogStatus.STARTED,
        )

        await self._get_active_company(request.empresa_id)

        try:
            card_is_valid = await self._verify_card(request, transaction_id)
        except CardServiceError as exc:
            return await self._register_failed_transaction(
                request, exc, transaction_id, elapsed_ms(start)
            )

        duration = elapsed_ms(start)
        transaction_status, liquidation_status = self._resolve_status(card_is_valid)

        if card_is_valid:
            logSuccess(
                LogEvent.PAYMENT_AUTHORIZED,
                module=_MODULE,
                message="Payment authorized by card provider",
                transaction_id=transaction_id,
                payment_provider=request.tipo_tarjeta.value,
                status=LogStatus.SUCCESS,
                duration_ms=duration,
            )
        else:
            logError(
                LogEvent.PAYMENT_DECLINED,
                module=_MODULE,
                message="Payment declined: card not found in provider",
                transaction_id=transaction_id,
                payment_provider=request.tipo_tarjeta.value,
                status=LogStatus.FAILED,
                error_code="PAYMENT_DECLINED",
                technical_detail="Card not found in provider",
                functional_detail="La tarjeta fue rechazada por el proveedor",
                duration_ms=duration,
            )

        return await self._save_transaction(
            request, transaction_status, liquidation_status, transaction_id, duration
        )

    async def _verify_card(self, request: CrearPagoRequest, transaction_id: str) -> bool:
        return await self.card_client.verify_card(
            card_type=request.tipo_tarjeta,
            card_number=request.numero_tarjeta,
            cvv=request.cvv,
            expiration_date=request.fecha_expiracion,
            transaction_id=transaction_id,
        )

    async def _register_failed_transaction(
        self,
        request: CrearPagoRequest,
        error: CardServiceError,
        transaction_id: str,
        duration: int,
    ) -> Transaccion:
        logError(
            LogEvent.PAYMENT_DECLINED,
            module=_MODULE,
            message="Payment failed: card service error",
            transaction_id=transaction_id,
            payment_provider=request.tipo_tarjeta.value,
            status=LogStatus.FAILED,
            error_code="CARD_SERVICE_ERROR",
            technical_detail=str(error),
            functional_detail="No se pudo completar la verificación con el proveedor de tarjetas",
            duration_ms=duration,
        )
        transaction = self._build_transaction(
            request=request,
            transaction_id=uuid.UUID(transaction_id),
            transaction_status=EstadoTransaccion.fallido,
            liquidation_status=None,
        )
        self.db.add(transaction)
        await self.db.flush()
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
        transaction_id: str,
        duration: int,
    ) -> Transaccion:
        transaction = self._build_transaction(
            request=request,
            transaction_id=uuid.UUID(transaction_id),
            transaction_status=transaction_status,
            liquidation_status=liquidation_status,
        )
        self.db.add(transaction)
        await self.db.flush()

        if transaction_status == EstadoTransaccion.aprobado:
            logSuccess(
                LogEvent.PAYMENT_CAPTURED,
                module=_MODULE,
                message="Payment captured and persisted",
                transaction_id=transaction_id,
                payment_provider=request.tipo_tarjeta.value,
                status=LogStatus.SUCCESS,
                duration_ms=duration,
            )

        return transaction

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
        transaction_id: uuid.UUID,
        transaction_status: EstadoTransaccion,
        liquidation_status: EstadoLiquidacion | None,
    ) -> Transaccion:
        return Transaccion(
            id=transaction_id,
            empresa_id=request.empresa_id,
            monto=request.monto,
            tipo_tarjeta=request.tipo_tarjeta,
            cliente_id=request.numero_tarjeta[-4:],
            estado_transaccion=transaction_status,
            estado_liquidacion=liquidation_status,
        )
