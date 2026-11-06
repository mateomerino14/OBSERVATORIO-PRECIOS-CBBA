"""Orquesta una corrida: recorre las páginas de una fuente y guarda sus precios."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from itertools import islice
from zoneinfo import ZoneInfo

import psycopg

from observatory.http_client import BotProtectionError
from observatory.models import FetchedPage
from observatory.storage import finish_run, save_observation, start_run

BOLIVIA_TZ = ZoneInfo("America/La_Paz")
# Si fallan tantas páginas seguidas, lo más probable es que la tienda cambió su sitio.
MAX_CONSECUTIVE_FAILURES = 10

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunSummary:
    """Resultado de una corrida de recolección."""

    run_id: int
    status: str
    pages_ok: int
    pages_failed: int
    observations: int


def today_in_bolivia() -> date:
    """Fecha actual en hora de Bolivia."""
    return datetime.now(BOLIVIA_TZ).date()


def collect(
    connection: psycopg.Connection,
    source: str,
    pages: Iterable[FetchedPage],
    observed_on: date,
    max_pages: int | None = None,
) -> RunSummary:
    """Guarda los precios de cada página y registra la corrida en la tabla ejecucion."""
    run_id = start_run(connection, source)
    pages_ok = 0
    pages_failed = 0
    observations = 0
    consecutive_failures = 0
    detail = None
    blocked = False
    try:
        for page in islice(pages, max_pages):
            if page.error is not None:
                pages_failed += 1
                consecutive_failures += 1
                logger.warning("%s: %s", page.label, page.error)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    detail = f"Se detuvo tras {consecutive_failures} fallos seguidos"
                    logger.error(detail)
                    break
                continue
            for observation in page.observations:
                save_observation(connection, observation, observed_on)
            observations += len(page.observations)
            pages_ok += 1
            consecutive_failures = 0
    except BotProtectionError as error:
        # Se respeta la protección de la tienda: no se reintenta en esta corrida.
        blocked = True
        detail = str(error)
        logger.error(detail)
    except Exception as error:
        pages_failed += 1
        detail = f"{type(error).__name__}: {error}"
        logger.exception("La corrida se interrumpió")
    status = finish_run(
        connection, run_id, pages_ok, pages_failed, observations, detail, blocked=blocked
    )
    logger.info(
        "Corrida %s: %s (%s páginas, %s con error, %s precios)",
        run_id,
        status,
        pages_ok,
        pages_failed,
        observations,
    )
    return RunSummary(run_id, status, pages_ok, pages_failed, observations)
