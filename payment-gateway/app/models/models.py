import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TipoTarjeta(str, enum.Enum):
    visa = "visa"
    mastercard = "mastercard"


class EstadoTransaccion(str, enum.Enum):
    aprobado = "aprobado"
    rechazado = "rechazado"
    fallido = "fallido"


class EstadoLiquidacion(str, enum.Enum):
    liquidado = "liquidado"
    no_liquidado = "no_liquidado"


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    transacciones: Mapped[list["Transaccion"]] = relationship(
        back_populates="empresa"
    )


class Transaccion(Base):
    __tablename__ = "transacciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False
    )
    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tipo_tarjeta: Mapped[TipoTarjeta] = mapped_column(
        Enum(TipoTarjeta), nullable=False
    )
    cliente_id: Mapped[str] = mapped_column(String(100), nullable=False)
    estado_transaccion: Mapped[EstadoTransaccion] = mapped_column(
        Enum(EstadoTransaccion), nullable=False
    )
    estado_liquidacion: Mapped[EstadoLiquidacion | None] = mapped_column(
        Enum(EstadoLiquidacion), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="transacciones")
