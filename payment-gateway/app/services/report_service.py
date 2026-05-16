import logging
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.models import Empresa, EstadoLiquidacion, Transaccion
from app.schemas.payment import ReportePendientesResponse, TransaccionReporteItem


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def obtener_pendientes(
        self,
        empresa_id: UUID,
        fecha_inicio: date | None,
        fecha_fin: date | None,
    ) -> ReportePendientesResponse:
        logger.info(
            "Generando reporte de pendientes",
            extra={"empresa_id": str(empresa_id), "fecha_inicio": str(fecha_inicio), "fecha_fin": str(fecha_fin)},
        )
        empresa = await self._validar_empresa(empresa_id)

        stmt = select(Transaccion).where(
            Transaccion.empresa_id == empresa_id,
            Transaccion.estado_liquidacion == EstadoLiquidacion.no_liquidado,
        )

        if fecha_inicio:
            dt_inicio = datetime.combine(fecha_inicio, time.min).replace(tzinfo=timezone.utc)
            stmt = stmt.where(Transaccion.creado_en >= dt_inicio)

        if fecha_fin:
            dt_fin = datetime.combine(fecha_fin, time.max).replace(tzinfo=timezone.utc)
            stmt = stmt.where(Transaccion.creado_en <= dt_fin)

        result = await self.db.execute(stmt)
        transacciones = result.scalars().all()

        total = sum((Decimal(str(t.monto)) for t in transacciones), Decimal("0"))
        logger.info(
            "Reporte generado",
            extra={"empresa_id": str(empresa_id), "cantidad": len(transacciones), "total_pendiente": str(total)},
        )

        return ReportePendientesResponse(
            empresa_id=empresa_id,
            empresa_nombre=empresa.nombre,
            cantidad=len(transacciones),
            total_pendiente=total,
            transacciones=[TransaccionReporteItem.model_validate(t) for t in transacciones],
        )

    async def _validar_empresa(self, empresa_id: UUID) -> Empresa:
        result = await self.db.execute(select(Empresa).where(Empresa.id == empresa_id))
        empresa = result.scalar_one_or_none()
        if empresa is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
        if not empresa.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
        return empresa
