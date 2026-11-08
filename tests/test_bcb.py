from datetime import date
from decimal import Decimal

import pytest

from observatory.sources.bcb import BcbParseError, ExchangeRate, parse_rates_pdf, pdf_url

# PDF de una página en blanco, sin tabla.
BLANK_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)


@pytest.fixture
def pdf_bytes(fixture_bytes):
    def read(year: int) -> bytes:
        return fixture_bytes(f"bcb_tipo_cambio_{year}.pdf")

    return read


def rates_by_day(content: bytes, year: int) -> dict[date, ExchangeRate]:
    return {rate.day: rate for rate in parse_rates_pdf(content, year)}


def test_pdf_url_includes_year() -> None:
    assert pdf_url(2026).endswith("pdf.php?anio=2026")


def test_reads_buy_and_sell_before_float(pdf_bytes) -> None:
    rates = rates_by_day(pdf_bytes(2025), 2025)

    assert rates[date(2025, 1, 2)] == ExchangeRate(
        date(2025, 1, 2), Decimal("6.96"), Decimal("6.86")
    )
    assert len(rates) == 247
    assert all(rate.sell == Decimal("6.96") for rate in rates.values())


@pytest.mark.parametrize(
    ("day", "sell"),
    [
        (date(2026, 6, 27), "9.73"),
        (date(2026, 7, 23), "11.13"),
        (date(2026, 8, 15), "11.58"),
        (date(2026, 9, 24), "12.26"),
        (date(2026, 11, 6), "11.89"),
    ],
)
def test_reads_single_official_rate_after_float(pdf_bytes, day: date, sell: str) -> None:
    rate = rates_by_day(pdf_bytes(2026), 2026)[day]

    assert (rate.sell, rate.buy) == (Decimal(sell), None)


def test_keeps_both_regimes_in_june_2026(pdf_bytes) -> None:
    rates = rates_by_day(pdf_bytes(2026), 2026)

    assert rates[date(2026, 6, 26)].buy == Decimal("6.86")
    assert rates[date(2026, 6, 27)].buy is None


def test_skips_days_without_quote(pdf_bytes) -> None:
    rates = rates_by_day(pdf_bytes(2026), 2026)

    assert date(2026, 1, 1) not in rates
    assert max(rates) == date(2026, 11, 6)


def test_rejects_pdf_without_table() -> None:
    with pytest.raises(BcbParseError):
        parse_rates_pdf(BLANK_PDF, 2026)
