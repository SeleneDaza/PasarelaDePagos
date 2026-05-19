import logging
logger = logging.getLogger("app.services.card_client")

async def _post_request(
    self,
    url: str,
    payload: dict,
    card_type: TipoTarjeta,
) -> httpx.Response:
    logger.info(
        f"Llamando servicio {card_type.value}",
        extra={"service": card_type.value, "url": url}
    )
    try:
        async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
        logger.info(
            f"Respuesta de {card_type.value}: {response.status_code}",
            extra={"service": card_type.value, "status": response.status_code}
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.error(
            f"Error de red con {card_type.value}: {exc}",
            extra={"service": card_type.value, "error": str(exc)}
        )
        raise CardServiceError(
            f"Error al comunicarse con el servicio {card_type.value}: {exc}"
        ) from exc

    self._raise_for_status(response, card_type)
    return response

def _raise_for_status(self, response: httpx.Response, card_type: TipoTarjeta) -> None:
    if response.status_code >= 500:
        logger.error(
            f"Error 5xx en {card_type.value}",
            extra={"service": card_type.value, "status": response.status_code}
        )
        raise CardServiceError(
            f"El servicio {card_type.value} respondió con error {response.status_code}"
        )
    if card_type == TipoTarjeta.nu and response.status_code == 400:
        logger.warning(
            f"Token invalido para Nu",
            extra={"service": "nu", "status": 400}
        )
        return
    response.raise_for_status()