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

    async def get_pending(
        self,
        company_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> ReportePendientesResponse:
        self._log_report_start(company_id, start_date, end_date)
        company = await self._validate_company(company_id)
        transactions = await self._get_pending_transactions(company_id, start_date, end_date)
        total = self._sum_amounts(transactions)
        self._log_report_complete(company_id, transactions, total)
        return self._build_report_response(company, transactions, total)

    def _log_report_start(
        self,
        company_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        logger.info(
            "Generando reporte de pendientes",
            extra={
                "empresa_id": str(company_id),
                "fecha_inicio": str(start_date),
                "fecha_fin": str(end_date),
            },
        )

    def _log_report_complete(
        self,
        company_id: UUID,
        transactions: list[Transaccion],
        total: Decimal,
    ) -> None:
        logger.info(
            "Reporte generado",
            extra={
                "empresa_id": str(company_id),
                "cantidad": len(transactions),
                "total_pendiente": str(total),
            },
        )

    async def _get_pending_transactions(
        self,
        company_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> list[Transaccion]:
        stmt = select(Transaccion).where(
            Transaccion.empresa_id == company_id,
            Transaccion.estado_liquidacion == EstadoLiquidacion.no_liquidado,
        )

        if start_date:
            start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
            stmt = stmt.where(Transaccion.creado_en >= start_dt)

        if end_date:
            end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
            stmt = stmt.where(Transaccion.creado_en <= end_dt)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    def _sum_amounts(self, transactions: list[Transaccion]) -> Decimal:
        return sum((Decimal(str(t.monto)) for t in transactions), Decimal("0"))

    def _build_report_response(
        self,
        company: Empresa,
        transactions: list[Transaccion],
        total: Decimal,
    ) -> ReportePendientesResponse:
        return ReportePendientesResponse(
            empresa_id=company.id,
            empresa_nombre=company.nombre,
            cantidad=len(transactions),
            total_pendiente=total,
            transacciones=[TransaccionReporteItem.model_validate(t) for t in transactions],
        )

    async def _validate_company(self, company_id: UUID) -> Empresa:
        result = await self.db.execute(select(Empresa).where(Empresa.id == company_id))
        company = result.scalar_one_or_none()
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
        if not company.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada.",
            )
        return company
