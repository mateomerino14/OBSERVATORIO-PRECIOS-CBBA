"""Canastas: definición desde TOML y emparejamiento de productos de tienda por reglas."""

import logging
import re
import tomllib
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import psycopg

BASE_UNITS = {"g", "ml", "u"}
PERIODS = {"semanal", "mensual"}
AUTOMATIC = "automatico"
RULE_CONFIDENCE = Decimal(1)

logger = logging.getLogger(__name__)


class BasketDefinitionError(ValueError):
    """El archivo de la canasta tiene un error de formato."""


@dataclass(frozen=True)
class BasketItem:
    """Producto canónico de la canasta con su cantidad y sus reglas de emparejamiento."""

    code: str
    name: str
    category: str
    unit: str
    quantity: Decimal
    include: tuple[re.Pattern, ...]
    exclude: tuple[re.Pattern, ...]
    subcategories: frozenset[str]
    min_content: Decimal | None
    max_content: Decimal | None


@dataclass(frozen=True)
class Basket:
    """Canasta completa leída del archivo."""

    code: str
    name: str
    description: str | None
    reference: str | None
    people: int
    period: str
    items: tuple[BasketItem, ...]


@dataclass(frozen=True)
class StoreProduct:
    """Lo necesario de un producto de tienda para decidir a qué ítem corresponde."""

    product_id: int
    name: str
    subcategory: str | None
    content: Decimal | None
    unit: str | None


def normalize(text: str) -> str:
    """Minúsculas y sin tildes, para que las reglas no dependan de cómo escribe la tienda."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def load_basket(path: Path) -> Basket:
    """Lee y valida un archivo TOML de canasta."""
    with path.open("rb") as file:
        data = tomllib.load(file)
    try:
        items = tuple(_parse_item(raw) for raw in data["producto"])
        basket = Basket(
            code=data["codigo"],
            name=data["nombre"],
            description=data.get("descripcion"),
            reference=data.get("referencia"),
            people=int(data["personas"]),
            period=data["periodo"],
            items=items,
        )
    except KeyError as error:
        raise BasketDefinitionError(f"{path.name}: falta el campo {error}") from error
    if basket.period not in PERIODS:
        raise BasketDefinitionError(f"{path.name}: periodo inválido {basket.period!r}")
    codes = [item.code for item in items]
    if len(codes) != len(set(codes)):
        raise BasketDefinitionError(f"{path.name}: hay códigos de producto repetidos")
    return basket


def matches(item: BasketItem, product: StoreProduct) -> bool:
    """Indica si un producto de tienda cumple las reglas de un ítem de la canasta."""
    if product.unit != item.unit or product.content is None:
        return False
    if item.subcategories and product.subcategory not in item.subcategories:
        return False
    if item.min_content is not None and product.content < item.min_content:
        return False
    if item.max_content is not None and product.content > item.max_content:
        return False
    name = normalize(product.name)
    if not any(pattern.search(name) for pattern in item.include):
        return False
    return not any(pattern.search(name) for pattern in item.exclude)


def assign(basket: Basket, products: list[StoreProduct]) -> dict[int, str]:
    """Asigna cada producto al primer ítem que lo acepta, en el orden del archivo."""
    assignments: dict[int, str] = {}
    for product in products:
        accepted = [item.code for item in basket.items if matches(item, product)]
        if not accepted:
            continue
        if len(accepted) > 1:
            logger.warning(
                "%s coincide con %s; se asigna a %s", product.name, accepted, accepted[0]
            )
        assignments[product.product_id] = accepted[0]
    return assignments


def sync_basket(connection: psycopg.Connection, basket: Basket) -> dict[str, int]:
    """Guarda la canasta y rehace sus emparejamientos automáticos; devuelve cuántos por ítem."""
    with connection.transaction():
        basket_id = _upsert_basket(connection, basket)
        canonical_ids = {item.code: _upsert_canonical(connection, item) for item in basket.items}
        connection.execute("DELETE FROM canasta_item WHERE canasta_id = %s", (basket_id,))
        for item in basket.items:
            connection.execute(
                "INSERT INTO canasta_item (canasta_id, producto_canonico_id, cantidad) "
                "VALUES (%s, %s, %s)",
                (basket_id, canonical_ids[item.code], item.quantity),
            )
        # Los emparejamientos manuales se respetan; los automáticos se recalculan.
        connection.execute(
            "DELETE FROM emparejamiento WHERE metodo = %s AND producto_canonico_id = ANY(%s)",
            (AUTOMATIC, list(canonical_ids.values())),
        )
        assignments = assign(basket, _unmatched_products(connection))
        for product_id, code in assignments.items():
            connection.execute(
                "INSERT INTO emparejamiento (producto_id, producto_canonico_id, metodo, confianza) "
                "VALUES (%s, %s, %s, %s)",
                (product_id, canonical_ids[code], AUTOMATIC, RULE_CONFIDENCE),
            )
    counts = {item.code: 0 for item in basket.items}
    for code in assignments.values():
        counts[code] += 1
    return counts


def _parse_item(raw: dict) -> BasketItem:
    """Convierte un [[producto]] del TOML, compilando sus expresiones regulares."""
    unit = raw["unidad"]
    if unit not in BASE_UNITS:
        raise BasketDefinitionError(f"{raw['codigo']}: unidad inválida {unit!r}")
    include = raw["incluir"]
    if not include:
        raise BasketDefinitionError(f"{raw['codigo']}: 'incluir' no puede estar vacío")
    try:
        include_patterns = tuple(re.compile(normalize(pattern)) for pattern in include)
        exclude_patterns = tuple(
            re.compile(normalize(pattern)) for pattern in raw.get("excluir", [])
        )
    except re.error as error:
        raise BasketDefinitionError(f"{raw['codigo']}: expresión inválida: {error}") from error
    return BasketItem(
        code=raw["codigo"],
        name=raw["nombre"],
        category=raw["categoria"],
        unit=unit,
        quantity=Decimal(str(raw["cantidad"])),
        include=include_patterns,
        exclude=exclude_patterns,
        subcategories=frozenset(raw.get("subcategorias", [])),
        min_content=_optional_decimal(raw.get("contenido_min")),
        max_content=_optional_decimal(raw.get("contenido_max")),
    )


def _optional_decimal(value: object) -> Decimal | None:
    """Decimal o None para los límites de presentación."""
    if value is None:
        return None
    return Decimal(str(value))


def _upsert_basket(connection: psycopg.Connection, basket: Basket) -> int:
    """Crea o actualiza la fila de la canasta."""
    return connection.execute(
        """
        INSERT INTO canasta (codigo, nombre, descripcion, referencia, personas, periodo)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (codigo) DO UPDATE SET
            nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion,
            referencia = EXCLUDED.referencia, personas = EXCLUDED.personas,
            periodo = EXCLUDED.periodo
        RETURNING id
        """,
        (
            basket.code,
            basket.name,
            basket.description,
            basket.reference,
            basket.people,
            basket.period,
        ),
    ).fetchone()[0]


def _upsert_canonical(connection: psycopg.Connection, item: BasketItem) -> int:
    """Crea o actualiza el producto canónico de un ítem."""
    return connection.execute(
        """
        INSERT INTO producto_canonico (codigo, nombre, categoria, unidad)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (codigo) DO UPDATE SET
            nombre = EXCLUDED.nombre, categoria = EXCLUDED.categoria, unidad = EXCLUDED.unidad
        RETURNING id
        """,
        (item.code, item.name, item.category, item.unit),
    ).fetchone()[0]


def _unmatched_products(connection: psycopg.Connection) -> list[StoreProduct]:
    """Productos de tienda sin emparejamiento (los manuales y de otras canastas quedan fuera)."""
    rows = connection.execute(
        """
        SELECT p.id, p.nombre, p.subcategoria, p.contenido_cantidad, p.contenido_unidad
        FROM producto p
        LEFT JOIN emparejamiento e ON e.producto_id = p.id
        WHERE e.producto_id IS NULL
        """
    ).fetchall()
    return [StoreProduct(*row) for row in rows]
