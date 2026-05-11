from fastapi import APIRouter
 
router = APIRouter(prefix="/mock", tags=["Mock (solo desarrollo)"])
 
TARJETAS_VISA = [
    {"numero_tarjeta": "4111111111111111", "cvv": "123"},
    {"numero_tarjeta": "4222222222222222", "cvv": "456"},
]
 
TARJETAS_MASTERCARD = [
    {"numero_tarjeta": "5111111111111118", "cvv": "321"},
    {"numero_tarjeta": "5222222222222220", "cvv": "654"},
]
 
 
@router.post("/visa/verificar-tarjeta")
def verificar_visa(numero_tarjeta: str, cvv: str):
    for t in TARJETAS_VISA:
        if t["numero_tarjeta"] == numero_tarjeta and t["cvv"] == cvv:
            return {"existe": True, "mensaje": "Tarjeta verificada correctamente"}
    return {"existe": False, "mensaje": "Tarjeta no encontrada"}
 
 
@router.post("/mastercard/verificar-tarjeta")
def verificar_mastercard(numero_tarjeta: str, cvv: str):
    for t in TARJETAS_MASTERCARD:
        if t["numero_tarjeta"] == numero_tarjeta and t["cvv"] == cvv:
            return {"existe": True, "mensaje": "Tarjeta verificada correctamente"}
    return {"existe": False, "mensaje": "Tarjeta no encontrada"}
 