"""Cliente HTTP cortés: respeta robots.txt, espera entre pedidos y reintenta con calma."""

import logging
import time
from collections.abc import Callable
from urllib import robotparser
from urllib.parse import urlsplit

import httpx

USER_AGENT = (
    "ObservatorioPreciosCBBA/0.1 (+https://github.com/mateomerino14/OBSERVATORIO-PRECIOS-CBBA)"
)
MIN_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 5.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

logger = logging.getLogger(__name__)


class DisallowedByRobotsError(PermissionError):
    """El robots.txt de la tienda no permite visitar esa URL."""


class PoliteClient:
    """Envoltura de httpx que aplica las reglas de recolección responsable del proyecto."""

    def __init__(
        self,
        delay_seconds: float = MIN_DELAY_SECONDS,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Prepara el cliente; la pausa nunca baja del mínimo del proyecto."""
        self.delay_seconds = max(delay_seconds, MIN_DELAY_SECONDS)
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-BO,es;q=0.9"},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            transport=transport,
        )

    def get_text(self, url: str) -> str:
        """Descarga una URL permitida y devuelve el cuerpo como texto."""
        if not self.is_allowed(url):
            raise DisallowedByRobotsError(f"robots.txt no permite: {url}")
        return self._fetch(url).text

    def is_allowed(self, url: str) -> bool:
        """Consulta el robots.txt del sitio, que se descarga una sola vez por sitio."""
        origin = _origin(url)
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        return self._robots[origin].can_fetch(USER_AGENT, url)

    def close(self) -> None:
        """Cierra las conexiones abiertas."""
        self._http.close()

    def _load_robots(self, origin: str) -> robotparser.RobotFileParser:
        """Descarga y lee el robots.txt; si no existe, se entiende que todo está permitido."""
        parser = robotparser.RobotFileParser()
        response = self._fetch(f"{origin}/robots.txt", raise_for_status=False)
        if response.status_code >= 400:
            parser.parse([])
            return parser
        parser.parse(response.text.splitlines())
        return parser

    def _fetch(self, url: str, raise_for_status: bool = True) -> httpx.Response:
        """Hace el pedido respetando la pausa y reintentando ante errores pasajeros."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_turn(url)
            response = self._http.get(url)
            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                break
            wait = BACKOFF_BASE_SECONDS * attempt
            logger.warning("HTTP %s en %s; reintento en %.0f s", response.status_code, url, wait)
            self._sleep(wait)
        if raise_for_status:
            response.raise_for_status()
        return response

    def _wait_turn(self, url: str) -> None:
        """Espera lo necesario para no pedir al mismo sitio antes de la pausa configurada."""
        origin = _origin(url)
        last = self._last_request_at.get(origin)
        if last is not None:
            remaining = self.delay_seconds - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at[origin] = self._clock()


def _origin(url: str) -> str:
    """Devuelve esquema y dominio de una URL."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
