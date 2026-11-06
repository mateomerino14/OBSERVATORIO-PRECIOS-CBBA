"""Orquesta una corrida: recorre URLs, interpreta cada página y guarda el resultado."""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from itertools import islice
from zoneinfo import ZoneInfo

import httpx
import psycopg

from observatory.http_client import DisallowedByRobotsError, PoliteClient
from observatory.models import PriceObservation
from observatory.storage import finish_run, save_observation, start_run

BOLIVIA_TZ = ZoneInfo("America/La_Paz")
# Si fallan tantas páginas seguidas, lo más probable es que la tienda cambió su sitio.
MAX_CONSECUTIVE_FAILURES = 20

logger = logging.getLogger(__name__)

PageParser = Callable[[str, str], PriceObservation]


@dataclass(frozen=True)
class RunSummary:
    """Resultado de una corrida de recolección."""

    run_id: int
    status: str
    pages_ok: int
    pages_failed: int


def today_in_bolivia() -> date:
    """Fecha actual en hora de Bolivia."""
    return datetime.now(BOLIVIA_TZ).date()


def collect(
    client: PoliteClient,
    connection: psycopg.Connection,
    source: str,
    urls: Iterable[str],
    parse_page: PageParser,
    observed_on: date,
    limit: int | None = None,
) -> RunSummary:
    """Recolecta las páginas indicadas y registra la corrida en la tabla ejecucion."""
    run_id = start_run(connection, source)
    pages_ok = 0
    pages_failed = 0
    consecutive_failures = 0
    detail = None
    try:
        for url in islice(urls, limit):
            try:
                observation = parse_page(client.get_text(url), url)
                save_observation(connection, observation, observed_on)
            except (httpx.HTTPError, DisallowedByRobotsError, ValueError) as error:
                pages_failed += 1
                consecutive_failures += 1
                logger.warning("No se pudo procesar %s: %s", url, error)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    detail = f"Se detuvo tras {consecutive_failures} fallos seguidos"
                    logger.error(detail)
                    break
                continue
            pages_ok += 1
            consecutive_failures = 0
    except Exception as error:
        # Un fallo fuera de una página (p. ej. el sitemap) cierra la corrida como fallida.
        pages_failed += 1
        detail = f"{type(error).__name__}: {error}"
        logger.exception("La corrida se interrumpió")
    status = finish_run(connection, run_id, pages_ok, pages_failed, detail)
    logger.info("Corrida %s: %s (%s ok, %s con error)", run_id, status, pages_ok, pages_failed)
    return RunSummary(run_id, status, pages_ok, pages_failed)
