import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.payment import ReportePendientesResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reportes", tags=["Reportes"])


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
        403: {"description": "Empresa no autorizada."},
        404: {"description": "Empresa no encontrada."},
        422: {"description": "Parámetros de entrada inválidos."},
    },
)
async def reporte_pendientes(
    empresa_id: uuid.UUID = Query(..., description="ID de la empresa a consultar."),
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
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_inicio no puede ser mayor a fecha_fin.",
        )

    service = ReportService(db)
    return await service.obtener_pendientes(empresa_id, fecha_inicio, fecha_fin)
