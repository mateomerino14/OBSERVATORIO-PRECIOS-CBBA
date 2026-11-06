"""Guardado idempotente de observaciones de precio y registro de corridas."""

from datetime import date

import psycopg

from observatory.models import PriceObservation
from observatory.units import parse_content

UPSERT_BRANCH = """
INSERT INTO sucursal (cadena_id, codigo, nombre, ciudad)
VALUES (%(chain_id)s, %(code)s, %(name)s, %(city)s)
ON CONFLICT (cadena_id, codigo) DO UPDATE SET nombre = EXCLUDED.nombre
RETURNING id
"""

UPSERT_PRODUCT = """
INSERT INTO producto (cadena_id, codigo_externo, nombre, marca,
                      contenido_cantidad, contenido_unidad, url)
VALUES (%(chain_id)s, %(external_code)s, %(name)s, %(brand)s,
        %(quantity)s, %(unit)s, %(url)s)
ON CONFLICT (cadena_id, codigo_externo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    marca = COALESCE(EXCLUDED.marca, producto.marca),
    contenido_cantidad = COALESCE(EXCLUDED.contenido_cantidad, producto.contenido_cantidad),
    contenido_unidad = COALESCE(EXCLUDED.contenido_unidad, producto.contenido_unidad),
    url = EXCLUDED.url,
    ultima_vez = now()
RETURNING id
"""

# Si el mismo día se recolecta dos veces, queda la última captura.
UPSERT_OBSERVATION = """
INSERT INTO observacion_precio (producto_id, sucursal_id, fecha, precio, precio_regular,
                                disponible, existencias)
VALUES (%(product_id)s, %(branch_id)s, %(observed_on)s, %(price)s, %(regular_price)s,
        %(available)s, %(stock)s)
ON CONFLICT (producto_id, sucursal_id, fecha) DO UPDATE SET
    precio = EXCLUDED.precio,
    precio_regular = EXCLUDED.precio_regular,
    disponible = EXCLUDED.disponible,
    existencias = EXCLUDED.existencias,
    capturado_en = now()
"""


class UnknownChainError(LookupError):
    """La cadena no está registrada en la tabla cadena."""


def get_chain_id(connection: psycopg.Connection, chain_code: str) -> int:
    """Busca el id de una cadena por su código."""
    row = connection.execute("SELECT id FROM cadena WHERE codigo = %s", (chain_code,)).fetchone()
    if row is None:
        raise UnknownChainError(f"Cadena no registrada: {chain_code}")
    return row[0]


def save_observation(
    connection: psycopg.Connection, observation: PriceObservation, observed_on: date
) -> None:
    """Guarda sucursal, producto y precio del día en una sola transacción."""
    content = parse_content(observation.name)
    quantity = None
    unit = None
    if content is not None:
        quantity = content.quantity
        unit = content.unit
    with connection.transaction():
        chain_id = get_chain_id(connection, observation.chain_code)
        branch_id = connection.execute(
            UPSERT_BRANCH,
            {
                "chain_id": chain_id,
                "code": observation.branch.code,
                "name": observation.branch.name,
                "city": observation.branch.city,
            },
        ).fetchone()[0]
        product_id = connection.execute(
            UPSERT_PRODUCT,
            {
                "chain_id": chain_id,
                "external_code": observation.external_code,
                "name": observation.name,
                "brand": observation.brand,
                "quantity": quantity,
                "unit": unit,
                "url": observation.url,
            },
        ).fetchone()[0]
        connection.execute(
            UPSERT_OBSERVATION,
            {
                "product_id": product_id,
                "branch_id": branch_id,
                "observed_on": observed_on,
                "price": observation.price,
                "regular_price": observation.regular_price,
                "available": observation.available,
                "stock": observation.stock,
            },
        )


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
    detail: str | None = None,
) -> str:
    """Cierra la corrida con su estado final según cuántas páginas fallaron."""
    status = "completada"
    if pages_failed > 0 and pages_ok > 0:
        status = "con_errores"
    elif pages_failed > 0 or pages_ok == 0:
        status = "fallida"
    with connection.transaction():
        connection.execute(
            """
            UPDATE ejecucion
            SET terminada_en = now(), estado = %s, paginas_ok = %s,
                paginas_error = %s, detalle = %s
            WHERE id = %s
            """,
            (status, pages_ok, pages_failed, detail, run_id),
        )
    return status
