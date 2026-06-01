import json
import time

import httpx

from app.config import settings
from app.models.models import TipoTarjeta
from app.structured_logger import LogEvent, LogStatus, elapsed_ms, logError, logInfo


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
        transaction_id: str = "",
    ) -> bool:
        url = self._urls[card_type]
        payload = self._build_payload(card_type, card_number, cvv, expiration_date)

        logInfo(
            LogEvent.PAYMENT_REQUEST_SENT,
            module=__name__,
            message=f"Sending card verification to {card_type.value}",
            transaction_id=transaction_id,
            payment_provider=card_type.value,
            status=LogStatus.SENT,
        )

        start = time.monotonic()
        response = await self._post_request(url, payload, card_type, transaction_id)
        duration = elapsed_ms(start)

        if card_type == TipoTarjeta.nu:
            result = response.text.strip() == "VALID"
        else:
            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                logError(
                    LogEvent.PAYMENT_DECLINED,
                    module=__name__,
                    message="Invalid JSON response from card service",
                    transaction_id=transaction_id,
                    payment_provider=card_type.value,
                    status=LogStatus.FAILED,
                    error_code="CARD_SERVICE_INVALID_RESPONSE",
                    technical_detail=str(exc),
                    functional_detail="El proveedor devolvió una respuesta inesperada",
                    duration_ms=duration,
                )
                raise CardServiceError(
                    f"El servicio {card_type.value} devolvió una respuesta no válida: {exc}"
                ) from exc

            if card_type == TipoTarjeta.mastercard:
                result = bool(data.get("exists", False))
            else:
                result = bool(data.get("existe", False))

        logInfo(
            LogEvent.PAYMENT_REQUEST_SENT,
            module=__name__,
            message=f"Card verification completed for {card_type.value}",
            transaction_id=transaction_id,
            payment_provider=card_type.value,
            status=LogStatus.SUCCESS,
            duration_ms=duration,
        )
        return result

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
        transaction_id: str = "",
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            logError(
                LogEvent.PAYMENT_DECLINED,
                module=__name__,
                message="Card service request timed out",
                transaction_id=transaction_id,
                payment_provider=card_type.value,
                status=LogStatus.FAILED,
                error_code="CARD_SERVICE_TIMEOUT",
                technical_detail=str(exc),
                functional_detail="El servicio de tarjetas no respondió a tiempo",
            )
            raise CardServiceError(
                f"Error al comunicarse con el servicio {card_type.value}: {exc}"
            ) from exc
        except httpx.NetworkError as exc:
            logError(
                LogEvent.PAYMENT_DECLINED,
                module=__name__,
                message="Card service network error",
                transaction_id=transaction_id,
                payment_provider=card_type.value,
                status=LogStatus.FAILED,
                error_code="CARD_SERVICE_NETWORK_ERROR",
                technical_detail=str(exc),
                functional_detail="No se pudo conectar con el servicio de verificación de tarjetas",
            )
            raise CardServiceError(
                f"Error al comunicarse con el servicio {card_type.value}: {exc}"
            ) from exc

        self._raise_for_status(response, card_type, transaction_id)
        return response

    def _raise_for_status(
        self,
        response: httpx.Response,
        card_type: TipoTarjeta,
        transaction_id: str = "",
    ) -> None:
        if response.status_code >= 500:
            logError(
                LogEvent.PAYMENT_DECLINED,
                module=__name__,
                message=f"Card service returned server error",
                transaction_id=transaction_id,
                payment_provider=card_type.value,
                status=LogStatus.FAILED,
                error_code=f"CARD_SERVICE_{response.status_code}",
                technical_detail=f"HTTP {response.status_code} from {card_type.value}",
                functional_detail="El servicio de tarjetas devolvió un error interno",
            )
            raise CardServiceError(
                f"El servicio {card_type.value} respondió con error {response.status_code}"
            )
        response.raise_for_status()
