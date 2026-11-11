"""Detección de precios anómalos: saltos propios de un producto, no del mercado entero.

Mercado (Defensoría, mensual):
- Cambio mensual de cada producto en logaritmo, solo entre meses consecutivos.
- Se le resta el cambio mediano de todos los productos ese mes: lo que queda es el movimiento
  propio del producto, sin la inflación ni el dólar que mueven a todos.
- Ese residuo se compara con la historia del mismo producto con el z-score modificado
  (mediana y MAD), robusto a los propios saltos. Se marca |z| >= 3,5 (Iglewicz y Hoaglin)
  si además el residuo pesa: al menos 10 % (en logaritmo) más o menos que el resto.

Supermercado (Hipermaxi, diario), solo productos de la canasta:
- Precio del último día contra la mediana de los días anteriores del mismo producto y sucursal.
- Se marca un cambio de 20 % o más, con al menos 7 días previos. Si el producto está en oferta
  se indica, porque una oferta explica la bajada.
"""

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import psycopg

from observatory.months import next_month

Z_THRESHOLD = 3.5
MAD_TO_SIGMA = 1.4826
MIN_CHANGES = 6
# En series muy estables la MAD es casi cero y cualquier centésimo daría un z enorme.
MIN_RESIDUAL = 0.10
DAILY_MIN_DAYS = 7
DAILY_WINDOW_DAYS = 14
DAILY_CHANGE = 0.20


@dataclass(frozen=True)
class MarketAnomaly:
    """Mes en que un producto de mercado se movió distinto al resto y a su historia."""

    product: str
    month: date
    change: float  # cambio del producto, 0,25 = +25 %
    common_change: float  # cambio mediano de todos los productos ese mes
    z: float


@dataclass(frozen=True)
class DailyAnomaly:
    """Precio del súper lejos de la mediana de sus días anteriores en la sucursal."""

    product_id: int
    name: str
    branch: str
    day: date
    price: Decimal
    previous_median: Decimal
    previous_days: int
    change: float
    on_offer: bool


def robust_z(values: list[float]) -> list[float]:
    """z-score modificado: distancia a la mediana en unidades de MAD (0 si no hay dispersión)."""
    center = statistics.median(values)
    mad = statistics.median(abs(value - center) for value in values) * MAD_TO_SIGMA
    if mad == 0:
        return [0.0 for _ in values]
    return [(value - center) / mad for value in values]


def monthly_log_changes(prices: dict[str, dict[date, Decimal]]) -> dict[str, dict[date, float]]:
    """Cambio en logaritmo de cada producto entre meses consecutivos con dato."""
    changes: dict[str, dict[date, float]] = {}
    for product, series in prices.items():
        product_changes = {}
        for month, price in series.items():
            following = next_month(month)
            if following in series:
                product_changes[following] = math.log(series[following] / price)
        changes[product] = product_changes
    return changes


def market_anomalies(
    prices: dict[str, dict[date, Decimal]], threshold: float = Z_THRESHOLD
) -> list[MarketAnomaly]:
    """Meses en que un producto se movió muy distinto al resto y a su propia historia."""
    changes = monthly_log_changes(prices)
    by_month: dict[date, list[float]] = defaultdict(list)
    for product_changes in changes.values():
        for month, change in product_changes.items():
            by_month[month].append(change)
    common = {month: statistics.median(values) for month, values in by_month.items()}
    anomalies = []
    for product, product_changes in changes.items():
        if len(product_changes) < MIN_CHANGES:
            continue
        months = sorted(product_changes)
        residuals = [product_changes[month] - common[month] for month in months]
        for month, residual, z in zip(months, residuals, robust_z(residuals), strict=True):
            if abs(z) >= threshold and abs(residual) >= MIN_RESIDUAL:
                anomalies.append(
                    MarketAnomaly(
                        product=product,
                        month=month,
                        change=math.exp(product_changes[month]) - 1,
                        common_change=math.exp(common[month]) - 1,
                        z=z,
                    )
                )
    anomalies.sort(key=lambda anomaly: abs(anomaly.z), reverse=True)
    return anomalies


def daily_anomalies(
    history: dict[tuple[int, str], dict[date, tuple[Decimal, bool]]],
    names: dict[int, str],
    day: date,
) -> list[DailyAnomaly]:
    """Precios de `day` a 20 % o más de la mediana previa del producto en la sucursal."""
    anomalies = []
    for (product_id, branch), series in history.items():
        if day not in series:
            continue
        previous = [price for when, (price, _) in series.items() if when < day]
        if len(previous) < DAILY_MIN_DAYS:
            continue
        price, on_offer = series[day]
        reference = statistics.median(previous)
        change = float(price / reference) - 1
        if abs(change) >= DAILY_CHANGE:
            anomalies.append(
                DailyAnomaly(
                    product_id=product_id,
                    name=names[product_id],
                    branch=branch,
                    day=day,
                    price=price,
                    previous_median=reference,
                    previous_days=len(previous),
                    change=change,
                    on_offer=on_offer,
                )
            )
    anomalies.sort(key=lambda anomaly: abs(anomaly.change), reverse=True)
    return anomalies


def load_market_prices(
    connection: psycopg.Connection, source: str, city: str
) -> dict[str, dict[date, Decimal]]:
    """Precios de mercado de una fuente y ciudad, por producto y mes."""
    prices: dict[str, dict[date, Decimal]] = defaultdict(dict)
    for product, month, price in connection.execute(
        "SELECT producto, mes, precio FROM precio_mercado WHERE fuente = %s AND ciudad = %s",
        (source, city),
    ):
        prices[product][month] = price
    return dict(prices)


DAILY_QUERY = """
SELECT o.producto_id, p.nombre, s.nombre, o.fecha, o.precio, o.precio_regular IS NOT NULL
FROM observacion_precio o
JOIN producto p ON p.id = o.producto_id
JOIN sucursal s ON s.id = o.sucursal_id
JOIN emparejamiento e ON e.producto_id = o.producto_id
WHERE o.fecha BETWEEN %s AND %s
"""


def load_daily_history(
    connection: psycopg.Connection, day: date
) -> tuple[dict[tuple[int, str], dict[date, tuple[Decimal, bool]]], dict[int, str], int]:
    """Precios de productos emparejados en la ventana, sus nombres y cuántos días hay."""
    start = day - timedelta(days=DAILY_WINDOW_DAYS)
    history: dict[tuple[int, str], dict[date, tuple[Decimal, bool]]] = defaultdict(dict)
    names: dict[int, str] = {}
    days: set[date] = set()
    for product_id, name, branch, when, price, on_offer in connection.execute(
        DAILY_QUERY, (start, day)
    ):
        history[(product_id, branch)][when] = (price, on_offer)
        names[product_id] = name
        days.add(when)
    return dict(history), names, len(days)
