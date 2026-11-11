from datetime import date
from decimal import Decimal

import pytest

from observatory.clusters import (
    NAME_JUMPED,
    NAME_KEPT_RISING,
    NAME_STABLE,
    cluster_market,
    dollar_phases,
    name_groups,
    previous_month,
    window_average,
)

MONTHS = [date(2024, 10, 1), date(2024, 11, 1), date(2024, 12, 1)] + [
    date(2025, month, 1) for month in range(1, 13)
]
PEAK = date(2025, 5, 1)

# Paralelo: sube de diciembre a mayo y baja hasta diciembre.
PARALLEL = {
    month: Decimal(str(value))
    for month, value in zip(
        MONTHS,
        [10.6, 10.7, 11.1, 11.3, 11.4, 12.4, 15.3, 16.4, 15.0, 14.0, 12.3, 12.6, 11.5, 10.1, 9.7],
        strict=True,
    )
}


def series(rise: float, fall: float, wiggle: float, seed: int) -> dict[date, Decimal]:
    """Precio que sube `rise` hasta mayo, cambia `fall` hasta diciembre y oscila `wiggle`."""
    result = {}
    for index, month in enumerate(MONTHS):
        if month <= PEAK:
            share = max(index - 2, 0) / 5
            level = 1 + rise * share
        else:
            share = (index - 7) / 7
            level = (1 + rise) * (1 + fall * share)
        # Patrón de período 3: cualquier ventana de tres meses lo promedia a cero.
        noise = 1 + wiggle * (0, 1, -1)[(index + seed) % 3]
        result[month] = Decimal(str(round(10 * level * noise, 4)))
    return result


def market() -> dict[str, dict[date, Decimal]]:
    """Tres grupos claros: estables, saltaron con el dólar y variables que siguen subiendo."""
    prices = {}
    for seed in range(5):
        prices[f"estable_{seed}"] = series(0.15 + 0.02 * seed, -0.05, 0.01, seed)
    for seed in range(3):
        prices[f"salto_{seed}"] = series(1.2 + 0.1 * seed, -0.1, 0.03, seed)
    for seed in range(4):
        prices[f"variable_{seed}"] = series(0.3, 0.35 + 0.03 * seed, 0.25, seed)
    return prices


def test_previous_month_crosses_the_year() -> None:
    assert previous_month(date(2025, 1, 1)) == date(2024, 12, 1)
    assert previous_month(date(2025, 6, 1)) == date(2025, 5, 1)


def test_window_average_centered_and_trailing() -> None:
    prices = {
        date(2025, 4, 1): Decimal(9),
        date(2025, 5, 1): Decimal(12),
        date(2025, 6, 1): Decimal(15),
    }
    assert window_average(prices, date(2025, 5, 1)) == pytest.approx(12)
    assert window_average(prices, date(2025, 6, 1), trailing=True) == pytest.approx(12)
    assert window_average(prices, date(2025, 6, 1)) == pytest.approx(13.5)
    assert window_average(prices, date(2026, 1, 1)) is None


def test_dollar_phases_start_in_december_and_end_with_market_data() -> None:
    phases = dollar_phases(PARALLEL, set(MONTHS))
    assert (phases.start, phases.peak, phases.end) == (
        date(2024, 12, 1),
        PEAK,
        date(2025, 12, 1),
    )
    # Si el pico es el último mes no hay bajada que medir.
    assert dollar_phases(PARALLEL, set(MONTHS[:8])) is None


def test_name_groups_by_their_centers() -> None:
    names = name_groups([(0.4, 0.3, 0.3), (0.1, 0.2, 0.0), (0.2, 1.2, -0.1)])
    assert names == [NAME_KEPT_RISING, NAME_STABLE, NAME_JUMPED]
    assert name_groups([(0.1, 0.2, 0.0), (0.4, 0.3, 0.3)]) == ["Grupo 1", "Grupo 2"]


def test_cluster_market_finds_the_three_groups() -> None:
    result = cluster_market(market(), PARALLEL)

    assert result.k == 3
    assert set(result.silhouettes) == {2, 3, 4, 5, 6}
    by_name = {group.name: set(group.products) for group in result.groups}
    assert by_name[NAME_STABLE] == {f"estable_{seed}" for seed in range(5)}
    assert by_name[NAME_JUMPED] == {f"salto_{seed}" for seed in range(3)}
    assert by_name[NAME_KEPT_RISING] == {f"variable_{seed}" for seed in range(4)}
    # Los grupos van de menor a mayor volatilidad.
    volatilities = [group.volatility for group in result.groups]
    assert volatilities == sorted(volatilities)
    assert result.labels["estable_0"] == 0
    jumped = next(group for group in result.groups if group.name == NAME_JUMPED)
    assert jumped.rise > 1


def test_cluster_market_needs_enough_products_and_phases() -> None:
    few = dict(list(market().items())[:5])
    assert cluster_market(few, PARALLEL) is None
    assert cluster_market(market(), {}) is None
