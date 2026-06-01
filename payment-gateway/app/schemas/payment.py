import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.models import EstadoLiquidacion, EstadoTransaccion, TipoTarjeta


def _parse_empresa_id(v: object) -> uuid.UUID:
    if isinstance(v, uuid.UUID):
        return v
    try:
        return uuid.UUID(str(v))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada.",
        )


# ---------- Entrada ----------

class CrearPagoRequest(BaseModel):
    """Body que recibe POST /pagos desde el sistema de venta de boletas."""

    empresa_id: uuid.UUID = Field(
        ...,
        description="ID de la empresa autorizada que recibirá el cobro.",
    )

    @field_validator("empresa_id", mode="before")
    @classmethod
    def validate_empresa_id(cls, v: object) -> uuid.UUID:
        return _parse_empresa_id(v)
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

    fecha_expiracion: str | None = Field(
    None,
    description="Fecha de expiración MM/AA. Requerida para Mastercard.",
    )

    @field_validator("numero_tarjeta")
    @classmethod
    def card_digits_only(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("El número de tarjeta debe contener solo dígitos.")
        return value

    @field_validator("cvv")
    @classmethod
    def cvv_digits_only(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("El CVV debe contener solo dígitos.")
        return value
    
class FaseResponse(BaseModel):
    numero: int
    tipo: str
    contenido: str


_FASES_INICIALES = [
    FaseResponse(numero=1, tipo="INFO", contenido="El sistema recibió tu solicitud y está preparando el pago."),
    FaseResponse(numero=2, tipo="INFO", contenido="Verificando que la empresa está autorizada para cobrar."),
    FaseResponse(numero=3, tipo="INFO", contenido="Consultando con Visa/Mastercard si la tarjeta existe."),
]

_FASE_4 = {
    EstadoTransaccion.aprobado:  FaseResponse(numero=4, tipo="INFO",  contenido="El servicio respondió: tarjeta aprobada."),
    EstadoTransaccion.rechazado: FaseResponse(numero=4, tipo="ERROR", contenido="El servicio respondió: tarjeta no encontrada."),
    EstadoTransaccion.fallido:   FaseResponse(numero=4, tipo="ERROR", contenido="No se pudo contactar con el servicio de tarjetas."),
}

_FASE_5 = {
    EstadoTransaccion.aprobado:  FaseResponse(numero=5, tipo="EXITO", contenido="Pago aprobado, reservando tu boleta."),
    EstadoTransaccion.rechazado: FaseResponse(numero=5, tipo="ERROR", contenido="Pago rechazado, no se realizó ningún cobro."),
    EstadoTransaccion.fallido:   FaseResponse(numero=5, tipo="ERROR", contenido="Pago rechazado, no se realizó ningún cobro."),
}


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

    @computed_field
    @property
    def fases(self) -> list[FaseResponse]:
        return [*_FASES_INICIALES, _FASE_4[self.estado_transaccion], _FASE_5[self.estado_transaccion]]

    @computed_field
    @property
    def success(self) -> bool:
        return self.estado_transaccion == EstadoTransaccion.aprobado

    @computed_field
    @property
    def message(self) -> str:
        return {
            EstadoTransaccion.aprobado: "Pago aprobado",
            EstadoTransaccion.rechazado: "Tarjeta rechazada.",
            EstadoTransaccion.fallido: "Error al procesar el pago. Intente más tarde.",
        }[self.estado_transaccion]


# ---------- Liquidación ----------

class LiquidacionBatchRequest(BaseModel):
    empresa_id: uuid.UUID | None = Field(
        None,
        description="ID de la empresa a liquidar. Si se omite, se liquidan todas las empresas.",
    )

    @field_validator("empresa_id", mode="before")
    @classmethod
    def validate_empresa_id(cls, v: object) -> uuid.UUID | None:
        if v is None:
            return None
        return _parse_empresa_id(v)


class LiquidacionBatchResponse(BaseModel):
    procesadas: int
    ids_liquidadas: list[uuid.UUID]
    ejecutado_en: datetime


# ---------- Reportes ----------

class TransaccionReporteItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monto: Decimal
    tipo_tarjeta: TipoTarjeta
    estado_transaccion: EstadoTransaccion
    creado_en: datetime


class ReportePendientesResponse(BaseModel):
    empresa_id: uuid.UUID
    empresa_nombre: str
    cantidad: int
    total_pendiente: Decimal
    transacciones: list[TransaccionReporteItem]