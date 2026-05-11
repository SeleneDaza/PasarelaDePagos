import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.models import EstadoLiquidacion, EstadoTransaccion, TipoTarjeta


# ---------- Entrada ----------

class CrearPagoRequest(BaseModel):
    """Body que recibe POST /pagos desde el sistema de venta de boletas."""

    empresa_id: uuid.UUID = Field(
        ...,
        description="ID de la empresa autorizada que recibirá el cobro.",
    )
    monto: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Monto a cobrar. Debe ser mayor a cero.",
    )
    tipo_tarjeta: TipoTarjeta = Field(
        ...,
        description="Franquicia de la tarjeta: 'visa' o 'mastercard'.",
    )
    numero_tarjeta: str = Field(
        ...,
        min_length=13,
        max_length=19,
        description="Número de tarjeta. No se persiste en la pasarela.",
    )
    cvv: str = Field(
        ...,
        min_length=3,
        max_length=4,
        description="Código de seguridad. No se persiste en la pasarela.",
    )

    @field_validator("numero_tarjeta")
    @classmethod
    def solo_digitos_tarjeta(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("El número de tarjeta debe contener solo dígitos.")
        return v

    @field_validator("cvv")
    @classmethod
    def solo_digitos_cvv(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("El CVV debe contener solo dígitos.")
        return v
    
class PagoResponse(BaseModel):
    """Respuesta de la pasarela al sistema de boletas tras procesar un pago."""
 
    model_config = ConfigDict(from_attributes=True)
 
    id: uuid.UUID
    empresa_id: uuid.UUID
    monto: Decimal
    tipo_tarjeta: TipoTarjeta
    estado_transaccion: EstadoTransaccion
    estado_liquidacion: EstadoLiquidacion | None
    creado_en: datetime