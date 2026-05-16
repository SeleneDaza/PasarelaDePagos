import httpx

from app.config import settings
from app.models.models import TipoTarjeta


class CardServiceError(Exception):
    """Error técnico al comunicarse con el servicio de tarjetas (timeout, 5xx, red)."""


class CardClient:
    """Cliente HTTP para los servicios serverless de Visa y Mastercard."""

    TIMEOUT_SECONDS = 5.0

    def __init__(self) -> None:
        self._urls = {
            TipoTarjeta.visa: f"{settings.VISA_SERVICE_URL}/visa/verificar-tarjeta",
            TipoTarjeta.mastercard: (
                f"{settings.MASTERCARD_SERVICE_URL}/mastercard/verificar-tarjeta"
            ),
        }

    async def verify_card(
        self,
        card_type: TipoTarjeta,
        card_number: str,
        cvv: str,
        expiration_date: str | None = None,
    ) -> bool:
        """
        Llama al servicio serverless correspondiente y devuelve si la tarjeta existe.

        Lanza CardServiceError si el servicio no responde o devuelve un error
        técnico. Una tarjeta que simplemente no existe NO es un error: devuelve False.
        """
        url = self._urls[card_type]
        payload = self._build_payload(card_type, card_number, cvv, expiration_date)
        response = await self._post_request(url, payload, card_type)
        data = response.json()
        return bool(data.get("existe", False))

    def _build_payload(
        self,
        card_type: TipoTarjeta,
        card_number: str,
        cvv: str,
        expiration_date: str | None,
    ) -> dict[str, str]:
        payload = {"numero_tarjeta": card_number, "cvv": cvv}
        if card_type == TipoTarjeta.mastercard and expiration_date:
            payload["fecha_expiracion"] = expiration_date
        return payload

    async def _post_request(
        self,
        url: str,
        payload: dict[str, str],
        card_type: TipoTarjeta,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise CardServiceError(
                f"Error al comunicarse con el servicio {card_type.value}: {exc}"
            ) from exc

        self._raise_for_status(response, card_type)
        return response

    def _raise_for_status(self, response: httpx.Response, card_type: TipoTarjeta) -> None:
        if response.status_code >= 500:
            raise CardServiceError(
                f"El servicio {card_type.value} respondió con error {response.status_code}"
            )

        response.raise_for_status()
