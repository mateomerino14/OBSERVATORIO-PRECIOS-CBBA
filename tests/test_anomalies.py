from datetime import date, timedelta
from decimal import Decimal

import pytest

from observatory.anomalies import (
    DAILY_MIN_DAYS,
    daily_anomalies,
    market_anomalies,
    monthly_log_changes,
    robust_z,
)

MONTHS = [date(2025, month, 1) for month in range(1, 13)]


def steady(start: float, growth: float, wiggle: float = 0.0) -> dict[date, Decimal]:
    """Serie que crece `growth` por mes, con una pequeña oscilación para que haya dispersión."""
    series = {}
    price = start
    for index, month in enumerate(MONTHS):
        series[month] = Decimal(str(round(price, 4)))
        price *= 1 + growth + wiggle * (-1) ** index
    return series


def test_robust_z_ignores_the_outlier_when_measuring_spread() -> None:
    z = robust_z([1.0, 1.1, 0.9, 1.0, 1.05, 0.95, 10.0])
    assert z[-1] > 20
    assert max(abs(value) for value in z[:-1]) < 2
    assert robust_z([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]


def test_monthly_changes_skip_missing_months() -> None:
    series = {
        date(2025, 1, 1): Decimal(10),
        date(2025, 2, 1): Decimal(11),
        date(2025, 4, 1): Decimal(12),
    }
    changes = monthly_log_changes({"arroz": series})["arroz"]
    assert list(changes) == [date(2025, 2, 1)]
    assert changes[date(2025, 2, 1)] == pytest.approx(0.0953, abs=1e-4)


def test_market_anomaly_is_a_jump_of_one_product_not_of_all() -> None:
    prices = {
        "arroz": steady(7.0, 0.01, 0.004),
        "azucar": steady(5.0, 0.01, 0.003),
        "fideo": steady(6.0, 0.01, 0.005),
        "cebolla": steady(30.0, 0.01, 0.006),
    }
    # Cebolla se duplica en agosto y vuelve en septiembre.
    prices["cebolla"][date(2025, 8, 1)] *= 2
    anomalies = market_anomalies(prices)
    found = {(anomaly.product, anomaly.month) for anomaly in anomalies}
    assert ("cebolla", date(2025, 8, 1)) in found
    assert ("cebolla", date(2025, 9, 1)) in found
    jump = next(a for a in anomalies if a.month == date(2025, 8, 1))
    assert jump.change == pytest.approx(1.0, abs=0.05)
    assert abs(jump.common_change) < 0.05
    assert all(anomaly.product == "cebolla" for anomaly in anomalies)


def test_a_shock_to_every_product_is_not_an_anomaly() -> None:
    prices = {
        "arroz": steady(7.0, 0.01, 0.004),
        "azucar": steady(5.0, 0.01, 0.003),
        "fideo": steady(6.0, 0.01, 0.005),
    }
    for series in prices.values():
        for month in MONTHS[6:]:
            series[month] *= Decimal("1.4")
    assert market_anomalies(prices) == []


def test_short_series_are_not_judged() -> None:
    prices = {"arroz": {month: Decimal(10 + index) for index, month in enumerate(MONTHS[:4])}}
    prices["arroz"][MONTHS[3]] = Decimal(100)
    assert market_anomalies(prices) == []


def daily_series(prices: list[str], last_offer: bool = False) -> dict[date, tuple[Decimal, bool]]:
    start = date(2026, 11, 1)
    series = {}
    for index, price in enumerate(prices):
        offer = last_offer and index == len(prices) - 1
        series[start + timedelta(days=index)] = (Decimal(price), offer)
    return series


def test_daily_anomaly_needs_enough_history_and_a_big_change() -> None:
    day = date(2026, 11, 1) + timedelta(days=DAILY_MIN_DAYS)
    history = {
        (1, "SACABA"): daily_series(["10"] * DAILY_MIN_DAYS + ["13"]),
        (2, "SACABA"): daily_series(["10"] * DAILY_MIN_DAYS + ["11"]),
        (3, "SACABA"): daily_series(["10"] * (DAILY_MIN_DAYS - 1) + ["14"]),
        (4, "SACABA"): daily_series(["20"] * DAILY_MIN_DAYS + ["12"], last_offer=True),
    }
    names = {1: "Arroz", 2: "Azúcar", 3: "Fideo", 4: "Aceite"}
    anomalies = daily_anomalies(history, names, day)
    assert [anomaly.product_id for anomaly in anomalies] == [4, 1]
    assert anomalies[0].on_offer
    assert anomalies[0].change == pytest.approx(-0.4)
    assert anomalies[1].previous_days == DAILY_MIN_DAYS
    assert anomalies[1].previous_median == Decimal(10)
