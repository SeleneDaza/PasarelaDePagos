import json
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
            TipoTarjeta.visa: f"{settings.VISA_SERVICE_URL}/verificar-tarjeta",
            TipoTarjeta.mastercard: f"{settings.MASTERCARD_SERVICE_URL}/verificar-tarjeta",
            TipoTarjeta.nu: f"{settings.NU_SERVICE_URL}/validate",
        }

    async def verify_card(
        self,
        card_type: TipoTarjeta,
        card_number: str,
        cvv: str,
        expiration_date: str | None = None,
    ) -> bool:
        url = self._urls[card_type]
        payload = self._build_payload(card_type, card_number, cvv, expiration_date)
        response = await self._post_request(url, payload, card_type)
        if card_type == TipoTarjeta.nu:
            return response.text.strip() == "VALID"
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise CardServiceError(
                f"El servicio {card_type.value} devolvió una respuesta no válida: {exc}"
            ) from exc
        if card_type == TipoTarjeta.mastercard:
            return bool(data.get("exists", False))
        return bool(data.get("existe", False))

    def _build_payload(
    self,
    card_type: TipoTarjeta,
    card_number: str,
    cvv: str,
    expiration_date: str | None,
    ) -> dict[str, str]:
        if card_type == TipoTarjeta.mastercard:
            return {"card_number": card_number, "cvv": cvv}
        if card_type == TipoTarjeta.nu:
            return {"number": card_number, "csv": cvv, "token": settings.NU_TOKEN}
        return {"numero_tarjeta": card_number, "cvv": cvv}

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