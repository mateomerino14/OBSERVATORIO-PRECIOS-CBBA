from datetime import date
from decimal import Decimal

import httpx
import psycopg
import pytest

from observatory.collector import MAX_CONSECUTIVE_FAILURES, collect, collect_exchange_rates
from observatory.http_client import BotProtectionError
from observatory.models import Branch, FetchedPage, PriceObservation

pytestmark = pytest.mark.db

TODAY = date(2026, 11, 6)
BRANCH = Branch(code="hipermaxi-sacaba", name="HIPERMAXI SACABA", city="cochabamba")


def observation(code: str) -> PriceObservation:
    return PriceObservation(
        chain_code="hipermaxi",
        branch=BRANCH,
        external_code=code,
        name=f"Producto {code} 1 kg",
        brand=None,
        url=f"https://hipermaxi.com/cochabamba/hipermaxi-sacaba/producto/{code}/x",
        price=Decimal("10.00"),
        regular_price=None,
        available=True,
        stock=None,
    )


def ok_page(*codes: str) -> FetchedPage:
    return FetchedPage(label="ok", observations=[observation(code) for code in codes])


def failed_page() -> FetchedPage:
    return FetchedPage(label="rota", error="HTTPStatusError: 500")


def stored_run(db: psycopg.Connection, run_id: int) -> tuple:
    return db.execute(
        "SELECT estado, paginas_ok, paginas_error, observaciones, detalle "
        "FROM ejecucion WHERE id = %s",
        (run_id,),
    ).fetchone()


def test_collect_saves_pages_and_counts_failures(db: psycopg.Connection) -> None:
    summary = collect(db, "hipermaxi", [ok_page("1", "2"), failed_page(), ok_page("3")], TODAY)

    assert (summary.status, summary.pages_ok, summary.pages_failed) == ("con_errores", 2, 1)
    assert summary.observations == 3
    assert db.execute("SELECT count(*) FROM observacion_precio").fetchone()[0] == 3
    assert stored_run(db, summary.run_id)[:4] == ("con_errores", 2, 1, 3)


def test_collect_respects_max_pages(db: psycopg.Connection) -> None:
    summary = collect(db, "hipermaxi", [ok_page("1"), ok_page("2")], TODAY, max_pages=1)

    assert (summary.status, summary.observations) == ("completada", 1)


def test_collect_stops_after_too_many_consecutive_failures(db: psycopg.Connection) -> None:
    pages = [failed_page() for _ in range(MAX_CONSECUTIVE_FAILURES + 5)]

    summary = collect(db, "hipermaxi", pages, TODAY)

    assert (summary.status, summary.pages_failed) == ("fallida", MAX_CONSECUTIVE_FAILURES)
    assert "fallos seguidos" in stored_run(db, summary.run_id)[4]


def test_collect_marks_run_blocked_on_bot_protection(db: psycopg.Connection) -> None:
    def pages():
        yield ok_page("1")
        raise BotProtectionError("Verificación antibots en https://hipermaxi.com/x")

    summary = collect(db, "hipermaxi", pages(), TODAY)

    assert (summary.status, summary.observations) == ("bloqueada", 1)
    assert "antibots" in stored_run(db, summary.run_id)[4]


def test_collect_records_failure_when_source_breaks(db: psycopg.Connection) -> None:
    def pages():
        raise ConnectionError("sin conexión")
        yield

    summary = collect(db, "hipermaxi", pages(), TODAY)

    assert summary.status == "fallida"
    assert "ConnectionError" in stored_run(db, summary.run_id)[4]


class FakeBcbClient:
    def __init__(self, files: dict[int, bytes]) -> None:
        self.files = files

    def get_bytes(self, url: str) -> bytes:
        year = int(url.rsplit("=", 1)[1])
        if year not in self.files:
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError("404", request=request, response=httpx.Response(404))
        return self.files[year]


def test_collect_exchange_rates_saves_years_and_reports_missing(
    db: psycopg.Connection, fixture_bytes
) -> None:
    client = FakeBcbClient({2026: fixture_bytes("bcb_tipo_cambio_2026.pdf")})

    summary = collect_exchange_rates(client, db, [2026, 2027])

    assert (summary.status, summary.pages_ok, summary.pages_failed) == ("con_errores", 1, 1)
    row = db.execute(
        "SELECT venta, compra FROM tipo_cambio "
        "WHERE fecha = '2026-09-24' AND fuente = 'bcb_oficial'"
    ).fetchone()
    assert row == (Decimal("12.26"), None)
    assert "2027" in stored_run(db, summary.run_id)[4]


def test_collect_exchange_rates_is_idempotent(db: psycopg.Connection, fixture_bytes) -> None:
    client = FakeBcbClient({2026: fixture_bytes("bcb_tipo_cambio_2026.pdf")})

    collect_exchange_rates(client, db, [2026])
    collect_exchange_rates(client, db, [2026])

    assert db.execute("SELECT count(*) FROM tipo_cambio").fetchone()[0] == 250
