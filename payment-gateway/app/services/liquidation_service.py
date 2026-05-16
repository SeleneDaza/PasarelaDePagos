import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.models import Empresa, EstadoLiquidacion, Transaccion
from app.schemas.payment import LiquidacionBatchResponse


class LiquidationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def liquidar_batch(self, empresa_id: UUID | None = None) -> LiquidacionBatchResponse:
        logger.info("Iniciando liquidación batch", extra={"empresa_id": str(empresa_id) if empresa_id else "todas"})
        if empresa_id is not None:
            await self._validar_empresa(empresa_id)

        stmt = select(Transaccion).where(
            Transaccion.estado_liquidacion == EstadoLiquidacion.no_liquidado
        )
        if empresa_id is not None:
            stmt = stmt.where(Transaccion.empresa_id == empresa_id)

        result = await self.db.execute(stmt)
        transacciones = result.scalars().all()

        ids = []
        for t in transacciones:
            t.estado_liquidacion = EstadoLiquidacion.liquidado
            ids.append(t.id)

        await self.db.flush()
        logger.info("Liquidación batch completada", extra={"procesadas": len(ids), "empresa_id": str(empresa_id) if empresa_id else "todas"})

        return LiquidacionBatchResponse(
            procesadas=len(ids),
            ids_liquidadas=ids,
            ejecutado_en=datetime.now(timezone.utc),
        )

    async def _validar_empresa(self, empresa_id: UUID) -> None:
        result = await self.db.execute(select(Empresa).where(Empresa.id == empresa_id))
        empresa = result.scalar_one_or_none()
        if empresa is None or not empresa.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
