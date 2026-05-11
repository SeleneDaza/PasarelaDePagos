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


class PaymentService:
    """Orquesta el flujo de crear pago: valida empresa, llama tarjeta, persiste."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.card_client = CardClient()

    async def crear_pago(self, payload: CrearPagoRequest) -> Transaccion:
        # 1. Validar que la empresa existe y está activa
        empresa = await self._obtener_empresa_activa(payload.empresa_id)

        # 2. Verificar la tarjeta con el servicio correspondiente
        try:
            tarjeta_valida = await self.card_client.verificar_tarjeta(
                tipo_tarjeta=payload.tipo_tarjeta,
                numero_tarjeta=payload.numero_tarjeta,
                cvv=payload.cvv,
            )
        except CardServiceError:
            # 3a. Falla técnica → estado_transaccion = fallido, sin liquidación
            transaccion = self._construir_transaccion(
                payload=payload,
                estado_transaccion=EstadoTransaccion.fallido,
                estado_liquidacion=None,
            )
            self.db.add(transaccion)
            await self.db.flush()
            return transaccion

        # 3b. Servicio respondió
        if tarjeta_valida:
            estado_transaccion = EstadoTransaccion.aprobado
            estado_liquidacion = EstadoLiquidacion.no_liquidado
        else:
            estado_transaccion = EstadoTransaccion.rechazado
            estado_liquidacion = None

        transaccion = self._construir_transaccion(
            payload=payload,
            estado_transaccion=estado_transaccion,
            estado_liquidacion=estado_liquidacion,
        )
        self.db.add(transaccion)
        await self.db.flush()
        return transaccion

    # ---------- Helpers privados ----------

    async def _obtener_empresa_activa(self, empresa_id) -> Empresa:
        result = await self.db.execute(
            select(Empresa).where(Empresa.id == empresa_id)
        )
        empresa = result.scalar_one_or_none()
        if empresa is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
        if not empresa.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no autorizada para cobrar.",
            )
        return empresa

    def _construir_transaccion(
        self,
        payload: CrearPagoRequest,
        estado_transaccion: EstadoTransaccion,
        estado_liquidacion: EstadoLiquidacion | None,
    ) -> Transaccion:
        # cliente_id es el ID que el cliente tiene en la BD de su tarjeta.
        # Por ahora usamos los últimos 4 dígitos como placeholder hasta que los
        # serverless devuelvan el ID real del cliente.
        return Transaccion(
            empresa_id=payload.empresa_id,
            monto=payload.monto,
            tipo_tarjeta=payload.tipo_tarjeta,
            cliente_id=payload.numero_tarjeta[-4:],
            estado_transaccion=estado_transaccion,
            estado_liquidacion=estado_liquidacion,
        )
