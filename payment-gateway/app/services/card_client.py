import httpx

from app.config import settings
from app.models.models import TipoTarjeta


class CardServiceError(Exception):
    """Error técnico al comunicarse con el servicio de tarjetas (timeout, 5xx, red)."""


class CardClient:
    """Cliente HTTP para los servicios serverless de Visa y Mastercard."""

    TIMEOUT_SEGUNDOS = 5.0

    def __init__(self) -> None:
        self._urls = {
            TipoTarjeta.visa: f"{settings.VISA_SERVICE_URL}/visa/verificar-tarjeta",
            TipoTarjeta.mastercard: (
                f"{settings.MASTERCARD_SERVICE_URL}/mastercard/verificar-tarjeta"
            ),
        }

    async def verificar_tarjeta(
        self,
        tipo_tarjeta: TipoTarjeta,
        numero_tarjeta: str,
        cvv: str,
    ) -> bool:
        """
        Llama al servicio serverless correspondiente y devuelve si la tarjeta existe.

        Lanza CardServiceError si el servicio no responde o devuelve un error
        técnico. Una tarjeta que simplemente no existe NO es un error: devuelve False.
        """
        url = self._urls[tipo_tarjeta]
        payload = {"numero_tarjeta": numero_tarjeta, "cvv": cvv}

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SEGUNDOS) as client:
                response = await client.post(url, params=payload)
                response.raise_for_status()
                data = response.json()
                return bool(data.get("existe", False))
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            raise CardServiceError(
                f"Error al comunicarse con el servicio {tipo_tarjeta.value}: {exc}"
            ) from exc
