from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.payment import LiquidacionBatchRequest, LiquidacionBatchResponse
from app.services.liquidation_service import LiquidationService

router = APIRouter(prefix="/liquidaciones", tags=["Liquidaciones"])


@router.post(
    "/batch",
    response_model=LiquidacionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Liquidación masiva de transacciones pendientes",
    description=(
        "Cambia el estado de todas las transacciones con `estado_liquidacion = no_liquidado` "
        "a `liquidado` en un solo proceso. Si se proporciona `empresa_id`, la liquidación "
        "aplica únicamente a esa empresa; de lo contrario, se procesan todas las empresas. "
        "Este mismo proceso se ejecuta automáticamente el primer día de cada mes a medianoche UTC."
    ),
    responses={
        200: {"description": "Liquidación ejecutada. Incluye cantidad e IDs de transacciones liquidadas."},
        404: {"description": "Empresa no encontrada."},
    },
)
async def liquidate_batch(
    payload: LiquidacionBatchRequest,
    db: AsyncSession = Depends(get_db),
) -> LiquidacionBatchResponse:
    service = LiquidationService(db)
    return await service.liquidate_batch(payload.empresa_id)
