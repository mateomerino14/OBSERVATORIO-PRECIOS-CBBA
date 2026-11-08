"""Guardado idempotente de observaciones de precio y registro de corridas."""

import json
from datetime import date
from decimal import Decimal

import psycopg

from observatory.models import PriceObservation
from observatory.units import Content, parse_content

PER_KILO = Content(quantity=Decimal(1000), unit="g")

UPSERT_BRANCH = """
INSERT INTO sucursal (cadena_id, codigo, nombre, ciudad, id_externo, direccion)
VALUES (%(chain_id)s, %(code)s, %(name)s, %(city)s, %(external_id)s, %(address)s)
ON CONFLICT (cadena_id, codigo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    id_externo = COALESCE(EXCLUDED.id_externo, sucursal.id_externo),
    direccion = COALESCE(EXCLUDED.direccion, sucursal.direccion)
RETURNING id
"""

# Productos y precios de una página en un solo viaje a la base: los datos van como JSON
# y se expanden con jsonb_to_recordset. Si el mismo día se recolecta dos veces, queda
# la última captura.
UPSERT_PAGE = """
WITH data AS (
    SELECT *
    FROM jsonb_to_recordset(%(rows)s::jsonb) AS x(
        external_code TEXT, name TEXT, brand TEXT, quantity NUMERIC, unit TEXT,
        sold_by_weight BOOLEAN, category TEXT, subcategory TEXT, url TEXT,
        price NUMERIC, regular_price NUMERIC, available BOOLEAN, stock INTEGER
    )
),
products AS (
    INSERT INTO producto (cadena_id, codigo_externo, nombre, marca, contenido_cantidad,
                          contenido_unidad, vendido_por_peso, categoria, subcategoria, url)
    SELECT %(chain_id)s, external_code, name, brand, quantity, unit, sold_by_weight,
           category, subcategory, url
    FROM data
    ON CONFLICT (cadena_id, codigo_externo) DO UPDATE SET
        nombre = EXCLUDED.nombre,
        vendido_por_peso = EXCLUDED.vendido_por_peso,
        categoria = COALESCE(EXCLUDED.categoria, producto.categoria),
        subcategoria = COALESCE(EXCLUDED.subcategoria, producto.subcategoria),
        marca = COALESCE(EXCLUDED.marca, producto.marca),
        contenido_cantidad = COALESCE(EXCLUDED.contenido_cantidad, producto.contenido_cantidad),
        contenido_unidad = COALESCE(EXCLUDED.contenido_unidad, producto.contenido_unidad),
        url = EXCLUDED.url,
        ultima_vez = now()
    RETURNING id, codigo_externo
)
INSERT INTO observacion_precio (producto_id, sucursal_id, fecha, precio, precio_regular,
                                disponible, existencias)
SELECT products.id, %(branch_id)s, %(observed_on)s, data.price, data.regular_price,
       data.available, data.stock
FROM data
JOIN products ON products.codigo_externo = data.external_code
ON CONFLICT (producto_id, sucursal_id, fecha) DO UPDATE SET
    precio = EXCLUDED.precio,
    precio_regular = EXCLUDED.precio_regular,
    disponible = EXCLUDED.disponible,
    existencias = EXCLUDED.existencias,
    capturado_en = now()
"""


class UnknownChainError(LookupError):
    """La cadena no está registrada en la tabla cadena."""


class MixedPageError(ValueError):
    """Una página trae observaciones de más de una cadena o sucursal."""


def get_chain_id(connection: psycopg.Connection, chain_code: str) -> int:
    """Busca el id de una cadena por su código."""
    row = connection.execute("SELECT id FROM cadena WHERE codigo = %s", (chain_code,)).fetchone()
    if row is None:
        raise UnknownChainError(f"Cadena no registrada: {chain_code}")
    return row[0]


def save_observation(
    connection: psycopg.Connection, observation: PriceObservation, observed_on: date
) -> None:
    """Guarda una sola observación (atajo de save_observations)."""
    save_observations(connection, [observation], observed_on)


def save_observations(
    connection: psycopg.Connection, observations: list[PriceObservation], observed_on: date
) -> int:
    """Guarda en una transacción las observaciones de una página, todas de la misma sucursal."""
    if not observations:
        return 0
    first = observations[0]
    for observation in observations:
        same_place = (
            observation.chain_code == first.chain_code and observation.branch == first.branch
        )
        if not same_place:
            raise MixedPageError("Todas las observaciones deben ser de la misma sucursal")
    # Un producto repetido en la página se guarda una vez, con su última captura.
    unique = {observation.external_code: observation for observation in observations}
    rows = [_to_row(observation) for observation in unique.values()]
    with connection.transaction():
        chain_id = get_chain_id(connection, first.chain_code)
        branch_id = connection.execute(
            UPSERT_BRANCH,
            {
                "chain_id": chain_id,
                "code": first.branch.code,
                "name": first.branch.name,
                "city": first.branch.city,
                "external_id": first.branch.external_id,
                "address": first.branch.address,
            },
        ).fetchone()[0]
        connection.execute(
            UPSERT_PAGE,
            {
                "rows": json.dumps(rows),
                "chain_id": chain_id,
                "branch_id": branch_id,
                "observed_on": observed_on,
            },
        )
    return len(rows)


def _to_row(observation: PriceObservation) -> dict[str, object]:
    """Fila JSON de una observación, con la presentación ya normalizada."""
    content = parse_content(observation.name)
    if observation.sold_by_weight:
        content = PER_KILO
    quantity = None
    unit = None
    if content is not None:
        quantity = str(content.quantity)
        unit = content.unit
    regular_price = None
    if observation.regular_price is not None:
        regular_price = str(observation.regular_price)
    return {
        "external_code": observation.external_code,
        "name": observation.name,
        "brand": observation.brand,
        "quantity": quantity,
        "unit": unit,
        "sold_by_weight": observation.sold_by_weight,
        "category": observation.category,
        "subcategory": observation.subcategory,
        "url": observation.url,
        "price": str(observation.price),
        "regular_price": regular_price,
        "available": observation.available,
        "stock": observation.stock,
    }


def start_run(connection: psycopg.Connection, source: str) -> int:
    """Registra el inicio de una corrida de recolección y devuelve su id."""
    with connection.transaction():
        row = connection.execute(
            "INSERT INTO ejecucion (fuente) VALUES (%s) RETURNING id", (source,)
        ).fetchone()
    return row[0]


def finish_run(
    connection: psycopg.Connection,
    run_id: int,
    pages_ok: int,
    pages_failed: int,
    observations: int = 0,
    detail: str | None = None,
    blocked: bool = False,
) -> str:
    """Cierra la corrida con su estado final según cuántas páginas fallaron."""
    status = "completada"
    if blocked:
        status = "bloqueada"
    elif pages_failed > 0 and pages_ok > 0:
        status = "con_errores"
    elif pages_failed > 0 or pages_ok == 0:
        status = "fallida"
    with connection.transaction():
        connection.execute(
            """
            UPDATE ejecucion
            SET terminada_en = now(), estado = %s, paginas_ok = %s,
                paginas_error = %s, observaciones = %s, detalle = %s
            WHERE id = %s
            """,
            (status, pages_ok, pages_failed, observations, detail, run_id),
        )
    return status


UPSERT_EXCHANGE_RATE = """
INSERT INTO tipo_cambio (fecha, fuente, compra, venta)
VALUES (%(day)s, %(source)s, %(buy)s, %(sell)s)
ON CONFLICT (fecha, fuente) DO UPDATE SET compra = EXCLUDED.compra, venta = EXCLUDED.venta
"""


def save_exchange_rates(connection: psycopg.Connection, source: str, rates: list) -> int:
    """Guarda o actualiza cotizaciones diarias de una fuente y devuelve cuántas procesó."""
    rows = [
        {"day": rate.day, "source": source, "buy": rate.buy, "sell": rate.sell} for rate in rates
    ]
    with connection.transaction(), connection.cursor() as cursor:
        cursor.executemany(UPSERT_EXCHANGE_RATE, rows)
    return len(rows)


UPSERT_MARKET_PRICE = """
INSERT INTO precio_mercado (fuente, ciudad, producto, mes, precio, presentacion_cantidad,
                            presentacion_unidad, descripcion, informe, verificado, fuente_url)
VALUES (%(fuente)s, %(ciudad)s, %(producto)s, %(mes)s, %(precio)s, %(presentacion_cantidad)s,
        %(presentacion_unidad)s, %(descripcion)s, %(informe)s, %(verificado)s, %(fuente_url)s)
ON CONFLICT (fuente, ciudad, producto, mes) DO UPDATE SET
    precio = EXCLUDED.precio,
    presentacion_cantidad = EXCLUDED.presentacion_cantidad,
    presentacion_unidad = EXCLUDED.presentacion_unidad,
    descripcion = EXCLUDED.descripcion,
    informe = EXCLUDED.informe,
    verificado = EXCLUDED.verificado,
    fuente_url = EXCLUDED.fuente_url
"""


def save_market_prices(connection: psycopg.Connection, rows: list[dict[str, object]]) -> int:
    """Guarda o actualiza precios de mercado mensuales y devuelve cuántos procesó."""
    with connection.transaction(), connection.cursor() as cursor:
        cursor.executemany(UPSERT_MARKET_PRICE, rows)
    return len(rows)
