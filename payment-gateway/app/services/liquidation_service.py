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

    async def liquidate_batch(self, company_id: UUID | None = None) -> LiquidacionBatchResponse:
        self._log_batch_start(company_id)
        if company_id is not None:
            await self._validate_company(company_id)

        transactions = await self._get_pending_transactions(company_id)
        ids = self._mark_as_liquidated(transactions)
        await self.db.flush()
        self._log_batch_complete(ids, company_id)
        return self._build_batch_response(ids)

    def _log_batch_start(self, company_id: UUID | None) -> None:
        logger.info(
            "Iniciando liquidación batch",
            extra={"empresa_id": str(company_id) if company_id else "todas"},
        )

    def _log_batch_complete(self, ids: list[UUID], company_id: UUID | None) -> None:
        logger.info(
            "Liquidación batch completada",
            extra={
                "procesadas": len(ids),
                "empresa_id": str(company_id) if company_id else "todas",
            },
        )

    async def _get_pending_transactions(self, company_id: UUID | None) -> list[Transaccion]:
        stmt = select(Transaccion).where(
            Transaccion.estado_liquidacion == EstadoLiquidacion.no_liquidado
        )
        if company_id is not None:
            stmt = stmt.where(Transaccion.empresa_id == company_id)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    def _mark_as_liquidated(self, transactions: list[Transaccion]) -> list[UUID]:
        ids: list[UUID] = []
        for transaction in transactions:
            transaction.estado_liquidacion = EstadoLiquidacion.liquidado
            ids.append(transaction.id)
        return ids

    def _build_batch_response(self, ids: list[UUID]) -> LiquidacionBatchResponse:
        return LiquidacionBatchResponse(
            procesadas=len(ids),
            ids_liquidadas=ids,
            ejecutado_en=datetime.now(timezone.utc),
        )

    async def _validate_company(self, company_id: UUID) -> None:
        result = await self.db.execute(select(Empresa).where(Empresa.id == company_id))
        company = result.scalar_one_or_none()
        if company is None or not company.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
