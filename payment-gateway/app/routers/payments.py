from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.payment import CrearPagoRequest, PagoResponse
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.post(
    "",
    response_model=PagoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo pago",
    description=(
        "Procesa un pago con tarjeta Visa o Mastercard. La pasarela enruta la "
        "transacción al servicio correspondiente, valida la tarjeta y registra "
        "el resultado. Las tarjetas rechazadas también quedan registradas."
    ),
    responses={
        201: {"description": "Pago procesado (aprobado, rechazado o fallido)."},
        404: {"description": "Empresa no encontrada o no autorizada."},
        422: {"description": "Datos de entrada inválidos."},
        502: {"description": "Servicio de tarjetas no disponible."},
    },
)
async def create_payment(
    payload: CrearPagoRequest,
    db: AsyncSession = Depends(get_db),
) -> PagoResponse:
    service = PaymentService(db)
    transaction = await service.create_payment(payload)
    return transaction
