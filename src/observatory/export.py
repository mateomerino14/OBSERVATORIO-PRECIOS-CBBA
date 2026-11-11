"""Exportación de los datos del dashboard a un JSON estático."""

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median

import psycopg

from observatory.basket import Basket, BasketItem
from observatory.sources.defensoria import PRODUCT_NAMES
from observatory.suggest import Suggestion, load_catalog, suggest

SCHEMA_VERSION = 1
CHAIN = "hipermaxi"
MARKET_SOURCE = "defensoria"
OFFICIAL_RATE = "bcb_oficial"
PARALLEL_RATE = "paralelo"
# Meses que se promedian para leer el mercado sin el ruido de un mes suelto.
MARKET_WINDOW = 3
MONTHS_IN_YEAR = 12
STORE_PRODUCTS_LIMIT = 60
# La unidad base se muestra por kilo o por litro; las unidades, por pieza.
DISPLAY_FACTOR = {"g": Decimal(1000), "ml": Decimal(1000), "u": Decimal(1)}
DISPLAY_UNIT = {"g": "kg", "ml": "litro", "u": "unidad"}
PRESENTATION_LABELS = {
    (Decimal(460), "g"): "1 libra",
    (Decimal(920), "g"): "2 libras",
    (Decimal(1000), "g"): "1 kg",
    (Decimal(2760), "g"): "1 cuartilla",
    (Decimal(350), "g"): "350 g",
    (Decimal(410), "g"): "envase 410 g",
    (Decimal(760), "g"): "sachet 760 g",
    (Decimal(946), "ml"): "bolsa 946 ml",
    (Decimal(1000), "ml"): "1 litro",
    (Decimal(1), "u"): "1 unidad",
    (Decimal(10), "u"): "10 unidades",
    (Decimal(25), "u"): "25 unidades",
}


def build_dashboard(connection: psycopg.Connection, basket: Basket, city: str) -> dict:
    """Arma el documento completo que lee el sitio."""
    latest_day = _latest_day(connection)
    market = _market_unit_prices(connection, city, basket)
    city_prices = _city_canonical_prices(connection)
    today_prices = city_prices.get(latest_day, {})
    return {
        "version": SCHEMA_VERSION,
        "generado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "ciudad": city,
        "ultimo_dia": _iso(latest_day),
        "ultima_corrida": _last_run(connection),
        "cobertura": _coverage(connection, latest_day),
        "canasta": _basket_summary(connection, basket, latest_day, city_prices),
        "canasta_mercado": _market_basket(basket, market, today_prices),
        "dolar": _exchange_rates(connection),
        "super_vs_mercado": _super_vs_market(connection, basket, market, today_prices, city),
        "subidas_mercado": _market_risers(connection, city),
        "productos": _products(connection, basket, market, today_prices, latest_day),
        "sugerencias": _suggestions(connection, basket),
    }


def _suggestion_row(suggestion: Suggestion) -> dict:
    product = suggestion.product
    return {
        "nombre": product.name,
        "subcategoria": product.subcategory,
        "similitud": round(suggestion.score, 2),
        "motivo": suggestion.reason,
        "url": product.url,
    }


def _suggestions(connection: psycopg.Connection, basket: Basket) -> dict | None:
    """Sugerencias del modelo de similitud para revisar las reglas de la canasta."""
    catalog = load_catalog(connection)
    if not catalog:
        return None
    report = suggest(basket, catalog)
    evaluation = report.evaluation
    median_rank = None
    if evaluation.median_rank is not None:
        median_rank = float(evaluation.median_rank)
    return {
        "productos_catalogo": report.catalog_size,
        "evaluacion": {
            "casos": evaluation.cases,
            "encontrados": evaluation.found_in_top,
            "top": evaluation.top,
            "puesto_mediano": median_rank,
        },
        "items": [
            {
                "codigo": item.code,
                "nombre": item.name,
                "aceptados": item.matched,
                "umbral": round(item.threshold, 2),
                "candidatos": [_suggestion_row(candidate) for candidate in item.candidates],
                "dudosos": [_suggestion_row(doubt) for doubt in item.doubtful],
            }
            for item in report.items
        ],
    }


def write_dashboard(document: dict, output: Path) -> Path:
    """Escribe el JSON del dashboard, creando la carpeta si hace falta."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=1, default=_json_default))
    return output


def presentation_label(quantity: Decimal, unit: str) -> str:
    """Nombre legible de una presentación ('1 libra', 'bolsa 946 ml')."""
    label = PRESENTATION_LABELS.get((quantity.normalize(), unit))
    if label is not None:
        return label
    return f"{quantity.normalize()} {unit}"


def market_cost(
    basket: Basket, unit_prices: dict[str, Decimal], codes: set[str] | None = None
) -> Decimal | None:
    """Costo de la canasta con precios por unidad base; None si falta algún producto pedido."""
    total = Decimal(0)
    for item in basket.items:
        if codes is not None and item.code not in codes:
            continue
        price = unit_prices.get(item.code)
        if price is None:
            return None
        total += item.quantity * price
    return total


def to_item_unit(item: BasketItem, price: Decimal, unit: str) -> Decimal | None:
    """Lleva un precio por unidad base de otra fuente a la unidad del ítem de la canasta."""
    if unit == item.unit:
        return price
    if unit == "u" and item.unit == "g" and item.unit_weight:
        return price / item.unit_weight
    return None


def _latest_day(connection: psycopg.Connection) -> date | None:
    """Último día con precios del supermercado."""
    return connection.execute("SELECT max(fecha) FROM observacion_precio").fetchone()[0]


def _last_run(connection: psycopg.Connection) -> dict | None:
    """Última corrida terminada del supermercado."""
    row = connection.execute(
        """
        SELECT iniciada_en, terminada_en, estado, paginas_ok, paginas_error, observaciones
        FROM ejecucion
        WHERE fuente = %s AND estado <> 'en_curso'
        ORDER BY iniciada_en DESC
        LIMIT 1
        """,
        (CHAIN,),
    ).fetchone()
    if row is None:
        return None
    keys = ("iniciada_en", "terminada_en", "estado", "paginas_ok", "paginas_error", "precios")
    return dict(zip(keys, row, strict=True))


def _coverage(connection: psycopg.Connection, latest_day: date | None) -> dict:
    """Cuántas sucursales, productos y días hay."""
    row = connection.execute(
        """
        SELECT count(DISTINCT sucursal_id) FILTER (WHERE fecha = %(day)s),
               count(DISTINCT producto_id) FILTER (WHERE fecha = %(day)s),
               count(DISTINCT fecha),
               min(fecha)
        FROM observacion_precio
        """,
        {"day": latest_day},
    ).fetchone()
    return {"sucursales": row[0], "productos": row[1], "dias": row[2], "primer_dia": _iso(row[3])}


def _basket_summary(
    connection: psycopg.Connection,
    basket: Basket,
    latest_day: date | None,
    city_prices: dict[date, dict[str, dict[str, Decimal]]],
) -> dict:
    """Costo diario de la canasta en la ciudad y, por sucursal, sobre los ítems que todas
    las sucursales tienen ese día (si no, una sucursal con más ítems parecería más cara)."""
    city = [
        {"fecha": _iso(day), **city_basket_cost(basket, prices)}
        for day, prices in sorted(city_prices.items())
    ]
    rows = connection.execute(
        """
        SELECT p.fecha, s.nombre, pc.codigo, p.precio_unitario_mediana, p.precio_unitario_minimo
        FROM precio_canonico_diario p
        JOIN producto_canonico pc ON pc.id = p.producto_canonico_id
        JOIN sucursal s ON s.id = p.sucursal_id
        """
    ).fetchall()
    quantities = {item.code: item.quantity for item in basket.items}
    by_day: dict[date, dict[str, dict[str, tuple[Decimal, Decimal]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for day, branch, code, typical, minimum in rows:
        if code in quantities:
            by_day[day][branch][code] = (Decimal(typical), Decimal(minimum))
    by_branch = []
    for day, branches in sorted(by_day.items()):
        common = set.intersection(*(set(codes) for codes in branches.values()))
        for branch, codes in sorted(branches.items()):
            by_branch.append(
                {
                    "fecha": _iso(day),
                    "sucursal": branch,
                    "tipico": _round(sum(quantities[c] * codes[c][0] for c in common)),
                    "economico": _round(sum(quantities[c] * codes[c][1] for c in common)),
                    "items": len(common),
                    "items_sucursal": len(codes),
                }
            )
    today = None
    if city and latest_day is not None and city[-1]["fecha"] == _iso(latest_day):
        today = city[-1]
    return {
        "codigo": basket.code,
        "nombre": basket.name,
        "personas": basket.people,
        "periodo": basket.period,
        "items_total": len(basket.items),
        "hoy": today,
        "ciudad_por_dia": city,
        "por_sucursal": by_branch,
    }


def _market_unit_prices(
    connection: psycopg.Connection, city: str, basket: Basket
) -> dict[date, dict[str, Decimal]]:
    """Precios de mercado por mes, llevados a la unidad de cada ítem de la canasta."""
    items = {item.code: item for item in basket.items}
    rows = connection.execute(
        """
        SELECT mes, producto, precio_unitario, unidad
        FROM precio_mercado_unitario
        WHERE fuente = %s AND ciudad = %s
        ORDER BY mes
        """,
        (MARKET_SOURCE, city),
    ).fetchall()
    months: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for month, product, price, unit in rows:
        item = items.get(product)
        if item is None:
            continue
        converted = to_item_unit(item, Decimal(price), unit)
        if converted is not None:
            months[month][product] = converted
    return dict(months)


def _city_canonical_prices(
    connection: psycopg.Connection,
) -> dict[date, dict[str, dict[str, Decimal]]]:
    """Mediana y mínimo por unidad base de cada producto canónico, por día, juntando todas
    las sucursales: así la ciudad tiene precio de un ítem aunque solo una sucursal lo venda."""
    rows = connection.execute(
        """
        SELECT o.fecha, pc.codigo, o.precio / p.contenido_cantidad
        FROM observacion_precio o
        JOIN producto p ON p.id = o.producto_id
        JOIN emparejamiento e ON e.producto_id = p.id
        JOIN producto_canonico pc ON pc.id = e.producto_canonico_id
        WHERE o.disponible AND p.contenido_cantidad > 0 AND p.contenido_unidad = pc.unidad
        """
    ).fetchall()
    values: dict[date, dict[str, list[Decimal]]] = defaultdict(lambda: defaultdict(list))
    for day, code, unit_price in rows:
        values[day][code].append(Decimal(unit_price))
    return {
        day: {
            code: {
                "tipico": Decimal(median(prices)),
                "minimo": min(prices),
                "productos": len(prices),
            }
            for code, prices in by_code.items()
        }
        for day, by_code in values.items()
    }


def city_basket_cost(basket: Basket, prices: dict[str, dict[str, Decimal]]) -> dict:
    """Costo de la canasta con precios de ciudad; los ítems sin precio no suman y se cuentan."""
    typical = Decimal(0)
    economic = Decimal(0)
    items = 0
    for item in basket.items:
        price = prices.get(item.code)
        if price is None:
            continue
        typical += item.quantity * price["tipico"]
        economic += item.quantity * price["minimo"]
        items += 1
    return {"tipico": _round(typical), "economico": _round(economic), "items": items}


def _market_basket(
    basket: Basket,
    market: dict[date, dict[str, Decimal]],
    today_prices: dict[str, dict[str, Decimal]],
) -> dict:
    """Costo mensual de la canasta en mercados: completa y solo con lo que vende el súper."""
    comparable = set(today_prices)
    months = [
        {
            "mes": _iso(month),
            "total": _round(market_cost(basket, prices)),
            "comparable": _round(market_cost(basket, prices, comparable)),
        }
        for month, prices in sorted(market.items())
    ]
    return {"productos_comparables": sorted(comparable), "por_mes": months}


def _exchange_rates(connection: psycopg.Connection) -> dict:
    """Dólar oficial (promedio mensual y último día) y paralelo (cierre mensual)."""
    official = connection.execute(
        """
        SELECT date_trunc('month', fecha)::date, avg(venta)
        FROM tipo_cambio WHERE fuente = %s
        GROUP BY 1 ORDER BY 1
        """,
        (OFFICIAL_RATE,),
    ).fetchall()
    parallel = connection.execute(
        """
        SELECT date_trunc('month', fecha)::date, venta
        FROM tipo_cambio WHERE fuente = %s ORDER BY fecha
        """,
        (PARALLEL_RATE,),
    ).fetchall()
    last = connection.execute(
        "SELECT fecha, venta FROM tipo_cambio WHERE fuente = %s ORDER BY fecha DESC LIMIT 1",
        (OFFICIAL_RATE,),
    ).fetchone()
    # El último día con compra publicada es el último del tipo de cambio fijo.
    fixed = connection.execute(
        """
        SELECT fecha, venta FROM tipo_cambio
        WHERE fuente = %s AND compra IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
        """,
        (OFFICIAL_RATE,),
    ).fetchone()
    today = None
    if last is not None:
        today = {"fecha": _iso(last[0]), "venta": _round(last[1])}
    fixed_end = None
    if fixed is not None:
        fixed_end = {"fecha": _iso(fixed[0]), "venta": _round(fixed[1])}
    return {
        "oficial_hoy": today,
        "fin_tipo_fijo": fixed_end,
        "oficial_mensual": [
            {"mes": _iso(month), "venta": _round(rate)} for month, rate in official
        ],
        "paralelo_mensual": [
            {"mes": _iso(month), "venta": _round(rate)} for month, rate in parallel
        ],
    }


def _super_vs_market(
    connection: psycopg.Connection,
    basket: Basket,
    market: dict[date, dict[str, Decimal]],
    today_prices: dict[str, dict[str, Decimal]],
    city: str,
) -> dict:
    """Súper hoy frente al promedio de los últimos meses de mercado, en la presentación de la
    Defensoría."""
    presentations = dict(
        (product, (Decimal(quantity), unit))
        for product, quantity, unit in connection.execute(
            """
            SELECT DISTINCT ON (producto) producto, presentacion_cantidad, presentacion_unidad
            FROM precio_mercado WHERE fuente = %s AND ciudad = %s
            ORDER BY producto, mes DESC
            """,
            (MARKET_SOURCE, city),
        )
    )
    window = _recent_window(sorted(market))
    rows = []
    for item in basket.items:
        today = today_prices.get(item.code)
        values = [market[month][item.code] for month in window if item.code in market[month]]
        if today is None or not values or item.code not in presentations:
            continue
        quantity, unit = presentations[item.code]
        # Presentación de la Defensoría expresada en la unidad del ítem.
        size = quantity
        if unit == "u" and item.unit == "g" and item.unit_weight:
            size = quantity * item.unit_weight
        market_price = sum(values) / len(values) * size
        typical = today["tipico"] * size
        rows.append(
            {
                "codigo": item.code,
                "nombre": item.name,
                "presentacion": presentation_label(quantity, unit),
                "mercado": _round(market_price),
                "super_tipico": _round(typical),
                "super_minimo": _round(today["minimo"] * size),
                "diferencia_pct": _round((typical / market_price - 1) * 100, 1),
            }
        )
    rows.sort(key=lambda row: row["diferencia_pct"], reverse=True)
    period = None
    if window:
        period = [_iso(window[0]), _iso(window[-1])]
    return {"periodo_mercado": period, "productos": rows}


def _market_risers(connection: psycopg.Connection, city: str) -> dict:
    """Variación de cada producto de mercado: últimos meses contra los mismos un año antes."""
    rows = connection.execute(
        "SELECT mes, producto, precio FROM precio_mercado WHERE fuente = %s AND ciudad = %s",
        (MARKET_SOURCE, city),
    ).fetchall()
    prices: dict[str, dict[date, Decimal]] = defaultdict(dict)
    for month, product, price in rows:
        prices[product][month] = price
    all_months = sorted({month for month, _, _ in rows})
    if not all_months:
        return {"periodo": None, "productos": []}
    recent = _recent_window(all_months)
    previous = [_shift_months(month, -MONTHS_IN_YEAR) for month in recent]
    result = []
    for product, series in prices.items():
        now = [series[month] for month in recent if month in series]
        before = [series[month] for month in previous if month in series]
        if not now or not before:
            continue
        change = (sum(now) / len(now)) / (sum(before) / len(before)) - 1
        result.append(
            {
                "codigo": product,
                "nombre": PRODUCT_NAMES[product],
                "variacion_pct": _round(change * 100, 1),
            }
        )
    result.sort(key=lambda row: row["variacion_pct"], reverse=True)
    return {
        "periodo": {"desde": [_iso(m) for m in previous], "hasta": [_iso(m) for m in recent]},
        "productos": result,
    }


def _products(
    connection: psycopg.Connection,
    basket: Basket,
    market: dict[date, dict[str, Decimal]],
    today_prices: dict[str, dict[str, Decimal]],
    latest_day: date | None,
) -> list[dict]:
    """Detalle de cada producto de la canasta: hoy, historia diaria, mercado y productos."""
    daily = defaultdict(list)
    for code, day, branch, typical, minimum in connection.execute(
        """
        SELECT pc.codigo, p.fecha, s.nombre, p.precio_unitario_mediana, p.precio_unitario_minimo
        FROM precio_canonico_diario p
        JOIN producto_canonico pc ON pc.id = p.producto_canonico_id
        JOIN sucursal s ON s.id = p.sucursal_id
        ORDER BY p.fecha, s.nombre
        """
    ):
        daily[code].append((day, branch, Decimal(typical), Decimal(minimum)))
    stores = defaultdict(list)
    for code, name, price, quantity, url, branches in connection.execute(
        """
        SELECT pc.codigo, p.nombre, min(o.precio), p.contenido_cantidad, p.url,
               count(DISTINCT o.sucursal_id)
        FROM observacion_precio o
        JOIN producto p ON p.id = o.producto_id
        JOIN emparejamiento e ON e.producto_id = p.id
        JOIN producto_canonico pc ON pc.id = e.producto_canonico_id
        WHERE o.fecha = %s AND o.disponible AND p.contenido_cantidad > 0
        GROUP BY pc.codigo, p.id
        """,
        (latest_day,),
    ):
        stores[code].append((name, price, Decimal(quantity), url, branches))
    products = []
    for item in basket.items:
        factor = DISPLAY_FACTOR[item.unit]
        today = today_prices.get(item.code)
        hoy = None
        if today is not None:
            hoy = {
                "tipico": _round(today["tipico"] * factor),
                "minimo": _round(today["minimo"] * factor),
                "productos": today["productos"],
            }
        store_rows = sorted(stores.get(item.code, []), key=lambda row: row[1] / row[2])
        products.append(
            {
                "codigo": item.code,
                "nombre": item.name,
                "categoria": item.category,
                "cantidad_canasta": _round(item.quantity, 3),
                "unidad": item.unit,
                "unidad_visible": DISPLAY_UNIT[item.unit],
                "hoy": hoy,
                "mercado_mensual": [
                    {"mes": _iso(month), "precio": _round(prices[item.code] * factor)}
                    for month, prices in sorted(market.items())
                    if item.code in prices
                ],
                "diario": [
                    {
                        "fecha": _iso(day),
                        "sucursal": branch,
                        "tipico": _round(typical * factor),
                        "minimo": _round(minimum * factor),
                    }
                    for day, branch, typical, minimum in daily.get(item.code, [])
                ],
                "tienda": [
                    {
                        "nombre": name,
                        "precio": _round(price),
                        "precio_unidad": _round(price / quantity * factor),
                        "sucursales": branches,
                        "url": url,
                    }
                    for name, price, quantity, url, branches in store_rows[:STORE_PRODUCTS_LIMIT]
                ],
            }
        )
    return products


def _recent_window(months: list[date]) -> list[date]:
    """Meses con datos dentro de los últimos MARKET_WINDOW meses calendario."""
    if not months:
        return []
    start = _shift_months(months[-1], -(MARKET_WINDOW - 1))
    return [month for month in months if month >= start]


def _shift_months(month: date, delta: int) -> date:
    """Primer día del mes desplazado delta meses."""
    index = month.year * MONTHS_IN_YEAR + month.month - 1 + delta
    return date(index // MONTHS_IN_YEAR, index % MONTHS_IN_YEAR + 1, 1)


def _round(value: Decimal | float | None, places: int = 2) -> float | None:
    """Redondea para el JSON; None se mantiene."""
    if value is None:
        return None
    return round(float(value), places)


def _iso(value: date | None) -> str | None:
    """Fecha en formato ISO o None."""
    if value is None:
        return None
    return value.isoformat()


def _json_default(value: object) -> object:
    """Convierte Decimal y fechas al serializar."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"No se puede serializar {type(value).__name__}")
