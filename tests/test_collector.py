from datetime import date

import httpx
import psycopg
import pytest

from observatory.collector import MAX_CONSECUTIVE_FAILURES, collect
from observatory.sources.hipermaxi import CHAIN_CODE, parse_product_page

pytestmark = pytest.mark.db

TODAY = date(2026, 11, 6)
BASE = "https://www.hipermaxi.com/cochabamba/hipermaxi-blanco-galindo/producto"
GOOD_URL = f"{BASE}/891816/arroz-familiar-caisy-1-kg"
OTHER_URL = f"{BASE}/005788/arroz-popular-hipermaxi-1-kg"
BROKEN_URL = f"{BASE}/000001/pagina-rota"


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def get_text(self, url: str) -> str:
        if url not in self.pages:
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError("404", request=request, response=httpx.Response(404))
        return self.pages[url]


def run(db: psycopg.Connection, client: FakeClient, urls) -> object:
    return collect(client, db, CHAIN_CODE, urls, parse_product_page, TODAY)


def test_collect_saves_good_pages_and_counts_failures(db, fixture_text) -> None:
    client = FakeClient(
        {
            GOOD_URL: fixture_text("hipermaxi_producto.html"),
            OTHER_URL: fixture_text("hipermaxi_producto_minimo.html"),
            BROKEN_URL: "<html><body>Mantenimiento</body></html>",
        }
    )

    summary = run(db, client, [GOOD_URL, BROKEN_URL, OTHER_URL])

    assert (summary.status, summary.pages_ok, summary.pages_failed) == ("con_errores", 2, 1)
    assert db.execute("SELECT count(*) FROM observacion_precio").fetchone()[0] == 2
    stored = db.execute(
        "SELECT estado, paginas_ok, paginas_error FROM ejecucion WHERE id = %s",
        (summary.run_id,),
    ).fetchone()
    assert stored == ("con_errores", 2, 1)


def test_collect_respects_limit(db, fixture_text) -> None:
    client = FakeClient({GOOD_URL: fixture_text("hipermaxi_producto.html")})

    summary = collect(
        client, db, CHAIN_CODE, [GOOD_URL, OTHER_URL], parse_product_page, TODAY, limit=1
    )

    assert (summary.status, summary.pages_ok) == ("completada", 1)


def test_collect_stops_after_too_many_consecutive_failures(db) -> None:
    urls = [f"{BASE}/{number:06d}/x" for number in range(MAX_CONSECUTIVE_FAILURES + 10)]

    summary = run(db, FakeClient({}), urls)

    assert summary.status == "fallida"
    assert summary.pages_failed == MAX_CONSECUTIVE_FAILURES
    detail = db.execute(
        "SELECT detalle FROM ejecucion WHERE id = %s", (summary.run_id,)
    ).fetchone()[0]
    assert "fallos seguidos" in detail


def test_collect_records_failure_when_discovery_breaks(db) -> None:
    def broken_discovery():
        raise httpx.ConnectError("sin conexión")
        yield

    summary = run(db, FakeClient({}), broken_discovery())

    assert summary.status == "fallida"
    detail = db.execute(
        "SELECT detalle FROM ejecucion WHERE id = %s", (summary.run_id,)
    ).fetchone()[0]
    assert "ConnectError" in detail
