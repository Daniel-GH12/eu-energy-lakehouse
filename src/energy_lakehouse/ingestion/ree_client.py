"""Cliente de ingesta para la API oficial de datos de Red Eléctrica (REE)."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

REE_PRICES_ENDPOINT = (
    "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
)


def _is_retryable_error(exc: BaseException) -> bool:
    """Indica si una excepción HTTP/red merece reintento automático.

    Solo se reintentan errores de transporte/red (`httpx.RequestError`) y
    respuestas HTTP transitorias (`429 Too Many Requests` o `5xx`). Los errores
    `4xx` del cliente (como `400` o `404`) fallan de inmediato.
    """
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception(_is_retryable_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def fetch_ree_prices(
    target_date: date,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Descarga los precios de mercado en tiempo real de REE para una fecha concreta.

    Args:
        target_date: Día objetivo a consultar en la API de REE.
        client: Cliente `httpx.Client` opcional para reutilizar conexiones
            TCP/TLS en llamadas consecutivas.

    Returns:
        Respuesta JSON completa devuelta por la API sin transformar.

    Raises:
        httpx.HTTPError: Si la petición falla tras los reintentos configurados
            o devuelve un código de estado HTTP de error (4xx/5xx).
    """
    date_str = target_date.isoformat()
    params = {
        "start_date": f"{date_str}T00:00",
        "end_date": f"{date_str}T23:59",
        "time_trunc": "hour",
    }

    logger.info("Solicitando precios REE para la fecha %s", date_str)
    if client is not None:
        response = client.get(REE_PRICES_ENDPOINT, params=params, timeout=10.0)
    else:
        response = httpx.get(REE_PRICES_ENDPOINT, params=params, timeout=10.0)
    response.raise_for_status()

    payload: dict[str, Any] = response.json()
    logger.info(
        "Descarga completada para %s (status=%s, series=%d)",
        date_str,
        response.status_code,
        len(payload.get("included", [])),
    )
    return payload


def save_to_bronze(
    payload: dict[str, Any],
    target_date: date,
    base_dir: Path = Path("data/bronze"),
) -> Path:
    """Persiste el payload crudo de REE en la capa Bronze particionada por fecha.

    Args:
        payload: Diccionario JSON tal como llega de la API.
        target_date: Fecha de la partición destino.
        base_dir: Directorio raíz de la capa Bronze.

    Returns:
        Ruta del archivo JSON guardado en disco.
    """
    output_path = (
        base_dir
        / "ree_prices"
        / f"date={target_date.isoformat()}"
        / "raw.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    logger.info("Payload guardado en capa Bronze: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    target_dates = [date(2025, 11, 1), date(2025, 11, 2)]
    with httpx.Client(timeout=10.0) as client:
        for day in target_dates:
            raw_payload = fetch_ree_prices(day, client=client)
            saved_path = save_to_bronze(raw_payload, day)
            logger.info(
                "Ingesta finalizada para %s -> %s", day.isoformat(), saved_path
            )
