"""Grupos de productos de mercado según cómo se movieron sus precios (k-means).

Cada producto de la Defensoría se describe con tres números:
- Volatilidad: MAD de sus cambios mensuales en logaritmo (robusta a un mes raro).
- Cambio en la subida del dólar paralelo: del primer diciembre con datos al mes del pico.
- Cambio en la bajada: del pico al último mes con datos.

Cada punto de las etapas es el promedio de tres meses (el mes y sus vecinos; el último, con los
dos anteriores), para que un sondeo ruidoso pese menos. Los tres números se estandarizan y se
agrupan con k-means; k se elige entre 2 y 6 por el índice de silueta, sin grupos de un solo
producto. Con 21 productos los grupos describen, no predicen.
"""

import math
import statistics
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from observatory.anomalies import MAD_TO_SIGMA, monthly_log_changes
from observatory.months import DECEMBER, next_month, previous_month, shift_months

K_OPTIONS = range(2, 7)
RANDOM_STATE = 0
N_INIT = 50
MIN_PRODUCTS = 8
MIN_CHANGES = 6
MIN_GROUP_SIZE = 2
MIN_PHASE_MONTHS = 3
# Los nombres de los grupos se deducen de sus centros solo con tres grupos.
NAMED_K = 3

NAME_STABLE = "Estables"
NAME_JUMPED = "Saltaron con la subida del dólar"
NAME_KEPT_RISING = "Variables, siguieron subiendo"


@dataclass(frozen=True)
class DollarPhases:
    """Inicio de la subida, pico y último mes del dólar paralelo."""

    start: date
    peak: date
    end: date


@dataclass(frozen=True)
class ProductProfile:
    """Los tres números con que se agrupa un producto."""

    product: str
    volatility: float
    rise: float  # cambio en la subida del dólar, 0,25 = +25 %
    fall: float  # cambio en la bajada del dólar


@dataclass(frozen=True)
class Group:
    """Un grupo con su nombre, sus productos y su centro en unidades originales."""

    number: int
    name: str
    products: tuple[str, ...]
    volatility: float
    rise: float
    fall: float


@dataclass(frozen=True)
class Clustering:
    """Resultado completo: etapas usadas, siluetas por k, grupos y perfiles."""

    phases: DollarPhases
    silhouettes: dict[int, float]
    k: int
    groups: tuple[Group, ...]
    profiles: tuple[ProductProfile, ...]
    labels: dict[str, int]


def dollar_phases(parallel: dict[date, Decimal], market_months: set[date]) -> DollarPhases | None:
    """Etapas del paralelo en los meses con datos de mercado: igual que los hallazgos del sitio."""
    months = sorted(month for month in parallel if month in market_months)
    if len(months) < MIN_PHASE_MONTHS:
        return None
    peak = max(months, key=lambda month: parallel[month])
    end = months[-1]
    decembers = [month for month in months if month.month == DECEMBER and month < peak]
    start = months[0]
    if decembers:
        start = decembers[0]
    if not start < peak < end:
        return None
    return DollarPhases(start=start, peak=peak, end=end)


def window_average(
    series: dict[date, Decimal], month: date, trailing: bool = False
) -> float | None:
    """Promedio del mes y sus vecinos con dato; con `trailing`, del mes y los dos anteriores."""
    window = (previous_month(month), month, next_month(month))
    if trailing:
        window = (shift_months(month, -2), previous_month(month), month)
    values = [float(series[when]) for when in window if when in series]
    if not values:
        return None
    return sum(values) / len(values)


def profiles(prices: dict[str, dict[date, Decimal]], phases: DollarPhases) -> list[ProductProfile]:
    """Perfil de cada producto con historia suficiente y dato en las tres etapas."""
    changes = monthly_log_changes(prices)
    result = []
    for product in sorted(prices):
        values = list(changes[product].values())
        if len(values) < MIN_CHANGES:
            continue
        start = window_average(prices[product], phases.start)
        peak = window_average(prices[product], phases.peak)
        end = window_average(prices[product], phases.end, trailing=True)
        if start is None or peak is None or end is None:
            continue
        center = statistics.median(values)
        volatility = statistics.median(abs(value - center) for value in values) * MAD_TO_SIGMA
        result.append(
            ProductProfile(
                product=product,
                volatility=volatility,
                rise=peak / start - 1,
                fall=end / peak - 1,
            )
        )
    return result


def features(items: list[ProductProfile]) -> np.ndarray:
    """Matriz estandarizada: volatilidad y cambios de cada etapa en logaritmo."""
    raw = np.array(
        [[item.volatility, math.log1p(item.rise), math.log1p(item.fall)] for item in items]
    )
    return StandardScaler().fit_transform(raw)


def name_groups(centers: list[tuple[float, float, float]]) -> list[str]:
    """Nombres por el centro de cada grupo (volatilidad, subida, bajada); solo con tres grupos."""
    if len(centers) != NAMED_K:
        return [f"Grupo {number + 1}" for number in range(len(centers))]
    names = [""] * NAMED_K
    stable = min(range(NAMED_K), key=lambda number: centers[number][0])
    names[stable] = NAME_STABLE
    others = [number for number in range(NAMED_K) if number != stable]
    jumped = max(others, key=lambda number: centers[number][1])
    names[jumped] = NAME_JUMPED
    for number in others:
        if number != jumped:
            names[number] = NAME_KEPT_RISING
    return names


def cluster_market(
    prices: dict[str, dict[date, Decimal]], parallel: dict[date, Decimal]
) -> Clustering | None:
    """Agrupa los productos de mercado; None si no hay datos suficientes."""
    market_months = {month for series in prices.values() for month in series}
    phases = dollar_phases(parallel, market_months)
    if phases is None:
        return None
    items = profiles(prices, phases)
    if len(items) < MIN_PRODUCTS:
        return None
    matrix = features(items)
    silhouettes = {}
    fits = {}
    for k in K_OPTIONS:
        if k >= len(items):
            break
        model = KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_STATE).fit(matrix)
        silhouettes[k] = float(silhouette_score(matrix, model.labels_))
        fits[k] = model.labels_
    # Un grupo de un solo producto no es un grupo: esos k no se eligen.
    eligible = [k for k in silhouettes if min(np.bincount(fits[k])) >= MIN_GROUP_SIZE]
    if not eligible:
        return None
    k = max(eligible, key=lambda option: silhouettes[option])
    labels = fits[k]
    members = [[items[i] for i in range(len(items)) if labels[i] == number] for number in range(k)]
    centers = [
        (
            statistics.mean(item.volatility for item in group),
            statistics.mean(item.rise for item in group),
            statistics.mean(item.fall for item in group),
        )
        for group in members
    ]
    names = name_groups(centers)
    # Orden estable para el sitio: de menor a mayor volatilidad.
    order = sorted(range(k), key=lambda number: centers[number][0])
    renumber = {old: new for new, old in enumerate(order)}
    groups = tuple(
        Group(
            number=renumber[old],
            name=names[old],
            products=tuple(item.product for item in members[old]),
            volatility=centers[old][0],
            rise=centers[old][1],
            fall=centers[old][2],
        )
        for old in order
    )
    return Clustering(
        phases=phases,
        silhouettes=silhouettes,
        k=k,
        groups=groups,
        profiles=tuple(items),
        labels={items[i].product: renumber[int(labels[i])] for i in range(len(items))},
    )
