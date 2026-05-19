from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/mock", tags=["Mock (solo desarrollo)"])

VISA_CARDS = [
    {"numero_tarjeta": "4111111111111111", "cvv": "123"},
    {"numero_tarjeta": "4222222222222222", "cvv": "456"},
]

MASTERCARD_CARDS = [
    {"numero_tarjeta": "5111111111111118", "cvv": "321"},
    {"numero_tarjeta": "5222222222222220", "cvv": "654"},
]

NU_CARDS = [
    {"number": "6011111111111117", "csv": "123"},
    {"number": "6011222233334444", "csv": "456"},
]


class VerificarTarjetaRequest(BaseModel):
    numero_tarjeta: str
    cvv: str


class VerificarNuRequest(BaseModel):
    number: str
    csv: str
    token: int


@router.post("/visa/verificar-tarjeta")
def verify_visa(body: VerificarTarjetaRequest):
    for card in VISA_CARDS:
        if card["numero_tarjeta"] == body.numero_tarjeta and card["cvv"] == body.cvv:
            return {"existe": True, "mensaje": "Tarjeta verificada correctamente"}
    return {"existe": False, "mensaje": "Tarjeta no encontrada"}


@router.post("/mastercard/verificar-tarjeta")
def verify_mastercard(body: VerificarTarjetaRequest):
    for card in MASTERCARD_CARDS:
        if card["numero_tarjeta"] == body.numero_tarjeta and card["cvv"] == body.cvv:
            return {"existe": True, "mensaje": "Tarjeta verificada correctamente"}
    return {"existe": False, "mensaje": "Tarjeta no encontrada"}


@router.post("/nu/verificar-tarjeta")
def verify_nu(body: VerificarNuRequest):
    if body.token != settings.NU_TOKEN:
        return "INVALID"
    for card in NU_CARDS:
        if card["number"] == body.number and card["csv"] == body.csv:
            return "VALID"
    return "INVALID"
