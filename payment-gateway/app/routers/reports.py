import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.payment import ReportePendientesResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _parse_company_id(empresa_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada.",
        )


def _validate_date_range(fecha_inicio: date | None, fecha_fin: date | None) -> None:
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_inicio no puede ser mayor a fecha_fin.",
        )


@router.get(
    "/pendientes",
    response_model=ReportePendientesResponse,
    summary="Reporte de transacciones pendientes de liquidación",
    description=(
        "Lista todas las transacciones aprobadas y aún no liquidadas de una empresa, "
        "junto con el monto total acumulado. El resultado siempre está filtrado por "
        "`empresa_id`, garantizando que cada empresa solo acceda a sus propios datos. "
        "Opcionalmente se puede acotar el resultado a un rango de fechas de creación."
    ),
    responses={
        200: {"description": "Reporte generado correctamente."},
        400: {"description": "Rango de fechas inválido (fecha_inicio > fecha_fin)."},
        404: {"description": "Empresa no encontrada."},
    },
)
async def get_pending_report(
    empresa_id: str = Query(..., description="ID (UUID) de la empresa a consultar."),
    fecha_inicio: date | None = Query(
        None,
        description="Fecha de inicio del rango (YYYY-MM-DD). Incluye todo el día.",
    ),
    fecha_fin: date | None = Query(
        None,
        description="Fecha de fin del rango (YYYY-MM-DD). Incluye todo el día.",
    ),
    db: AsyncSession = Depends(get_db),
) -> ReportePendientesResponse:
    company_id = _parse_company_id(empresa_id)
    _validate_date_range(fecha_inicio, fecha_fin)
    service = ReportService(db)
    return await service.get_pending(company_id, fecha_inicio, fecha_fin)
