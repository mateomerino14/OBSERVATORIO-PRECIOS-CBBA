"""Fuente Hipermaxi: sucursales y productos desde la API pública de su tienda en línea."""

import json
import logging
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx
from selectolax.lexbor import LexborHTMLParser

from observatory.models import Branch, FetchedPage, PriceObservation

CHAIN_CODE = "hipermaxi"
SITE_BASE = "https://hipermaxi.com"
WEB_BASE = "https://www.hipermaxi.com"
API_BASE = f"{SITE_BASE}/tienda-api/api/v1/public"
PAGE_SIZE = 50
ALL_MARKETS = 0
SUPERMARKET_SERVICE_TYPE = 1
SUPERMARKET_PREFIX = "HIPERMAXI"
WEIGHT_UNIT = "KGM"
TREE_PAGE_CATEGORY = "abarrotes"
# Rubros de la canasta: 1 abarrotes y bebidas, 2 frescos, 3 hogar y cuidado personal,
# 6 frutas, verduras y granos. Se excluye el 4: bazar, juguetería y textiles.
CANASTA_RUBROS = frozenset({1, 2, 3, 6})
CATEGORY_TREE_START = '[{"idCategory"'
CENT = Decimal("0.01")

logger = logging.getLogger(__name__)


class HipermaxiApiError(ValueError):
    """La API respondió con error o con un formato inesperado."""


@dataclass(frozen=True)
class HipermaxiBranch:
    """Sucursal con los dos identificadores que pide la API."""

    market_id: int
    branch_id: int
    branch: Branch


@dataclass(frozen=True)
class Subcategory:
    """Subcategoría del catálogo."""

    subcategory_id: int
    name: str


@dataclass(frozen=True)
class Category:
    """Categoría del catálogo con su rubro y subcategorías."""

    category_id: int
    name: str
    rubro: int
    subcategories: tuple[Subcategory, ...]


def slugify(text: str) -> str:
    """Convierte un texto al formato de URL que usa la tienda: 'Picaña 1 kg' -> 'picana-1-kg'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def unwrap(payload: object) -> list[dict]:
    """Devuelve la lista Dato de una respuesta de la API o falla si trae error."""
    if not isinstance(payload, dict):
        raise HipermaxiApiError("Respuesta de la API sin formato de objeto")
    if payload.get("ConError") or payload.get("Estado") != httpx.codes.OK:
        raise HipermaxiApiError(f"La API respondió con error: {payload.get('Mensaje')}")
    data = payload.get("Dato")
    if data is None:
        return []
    if not isinstance(data, list):
        raise HipermaxiApiError("El campo Dato no es una lista")
    return data


def find_region_id(client, city: str) -> int:
    """Busca el id de región de una ciudad entre las que atiende Hipermaxi."""
    for region in unwrap(client.get_json(f"{API_BASE}/markets/ciudades")):
        if slugify(region["Nombre"]) == city:
            return int(region["IdRegion"])
    raise HipermaxiApiError(f"Hipermaxi no atiende la ciudad: {city}")


def list_branches(client, city: str) -> list[HipermaxiBranch]:
    """Lista los supermercados de una ciudad, sin farmacias."""
    region_id = find_region_id(client, city)
    params = {"IdMarket": ALL_MARKETS, "IdTipoServicio": SUPERMARKET_SERVICE_TYPE}
    branches = []
    for market in unwrap(client.get_json(f"{API_BASE}/markets/activos", params)):
        if market.get("IdRegion") != region_id:
            continue
        for location in market.get("Locatarios", []):
            name = str(location.get("Descripcion", "")).strip()
            is_supermarket = location.get("IdTipoServicio") == SUPERMARKET_SERVICE_TYPE
            if not is_supermarket or not name.upper().startswith(SUPERMARKET_PREFIX):
                continue
            branch = Branch(
                code=slugify(name),
                name=name,
                city=city,
                external_id=str(location["IdSucursal"]),
                address=location.get("Direccion"),
            )
            branches.append(
                HipermaxiBranch(int(market["IdMarket"]), int(location["IdSucursal"]), branch)
            )
    return branches


def parse_category_tree(html: str) -> list[Category]:
    """Extrae el árbol de categorías que Next.js deja dentro del HTML de la página."""
    tree = LexborHTMLParser(html)
    for script in tree.css("script"):
        text = script.text()
        if "self.__next_f.push(" not in text or "idCategory" not in text:
            continue
        for chunk in _flight_chunks(text):
            raw = _balanced_array(chunk, chunk.find(CATEGORY_TREE_START))
            if raw is None:
                continue
            return [_to_category(item) for item in json.loads(raw)]
    raise HipermaxiApiError("La página no trae el árbol de categorías")


def fetch_category_tree(client, city: str, branch_code: str) -> list[Category]:
    """Descarga una página de categoría de la sucursal y lee de ella el árbol completo."""
    url = f"{WEB_BASE}/{city}/{branch_code}/categoria/{TREE_PAGE_CATEGORY}"
    return parse_category_tree(client.get_text(url))


def to_observation(
    item: dict, city: str, branch: Branch, category: str | None, subcategory: str | None
) -> PriceObservation:
    """Convierte un producto de la API en una observación de precio."""
    name = str(item.get("Descripcion") or "").strip()
    code = str(item.get("IdProducto") or "").strip()
    sale_price = _to_decimal(item.get("PrecioVenta"))
    if not name or not code or sale_price is None or sale_price <= 0:
        raise HipermaxiApiError(f"Producto incompleto: {item.get('IdProducto')}")

    price = sale_price
    regular_price = None
    offer_price = _to_decimal(item.get("PrecioOferta"))
    if item.get("ConOferta") and offer_price is not None and 0 < offer_price < sale_price:
        price = offer_price
        regular_price = sale_price
    original = _to_decimal(item.get("PrecioOriginal"))
    if regular_price is not None and original is not None and original > regular_price:
        regular_price = original

    stock_value = _to_decimal(item.get("Stock"))
    stock = None
    if item.get("VerStock") and stock_value is not None and stock_value >= 0:
        stock = int(stock_value)
    available = True
    if item.get("ControlStock") and stock_value is not None and stock_value <= 0:
        available = False

    return PriceObservation(
        chain_code=CHAIN_CODE,
        branch=branch,
        external_code=code,
        name=name,
        brand=None,
        url=f"{SITE_BASE}/{city}/{branch.code}/producto/{code}/{slugify(name)}",
        price=price,
        regular_price=regular_price,
        available=available,
        stock=stock,
        category=category,
        subcategory=subcategory,
        sold_by_weight=item.get("UnidadMedida") == WEIGHT_UNIT,
    )


def iter_pages(client, city: str, rubros: frozenset[int] = CANASTA_RUBROS) -> Iterator[FetchedPage]:
    """Recorre todas las sucursales de la ciudad, subcategoría por subcategoría."""
    branches = list_branches(client, city)
    if not branches:
        raise HipermaxiApiError(f"No hay supermercados Hipermaxi en {city}")
    logger.info("Sucursales en %s: %s", city, ", ".join(item.branch.name for item in branches))
    categories = _load_tree_or_none(client, city, branches[0].branch.code)

    for target in branches:
        base_params = {"IdMarket": target.market_id, "IdLocatario": target.branch_id}
        if categories is None:
            yield from _paginate(client, city, target.branch, base_params, None, None)
            continue
        for category in categories:
            if category.rubro not in rubros:
                continue
            for subcategory in category.subcategories:
                params = {
                    **base_params,
                    "IdCategoria": category.category_id,
                    "IdsSubcategoria": subcategory.subcategory_id,
                }
                yield from _paginate(
                    client, city, target.branch, params, category.name, subcategory.name
                )


def _load_tree_or_none(client, city: str, branch_code: str) -> list[Category] | None:
    """Intenta leer el árbol de categorías; sin él se recorre el catálogo completo sin categoría."""
    try:
        categories = fetch_category_tree(client, city, branch_code)
    except (httpx.HTTPError, HipermaxiApiError) as error:
        logger.warning("Sin árbol de categorías (%s); se recorre el catálogo completo", error)
        return None
    logger.info("Árbol de categorías: %s categorías", len(categories))
    return categories


def _paginate(
    client,
    city: str,
    branch: Branch,
    params: dict[str, int],
    category: str | None,
    subcategory: str | None,
) -> Iterator[FetchedPage]:
    """Pide las páginas de un listado hasta que una venga incompleta."""
    page = 1
    while True:
        label = f"{branch.name} / {subcategory or 'catálogo'} / página {page}"
        query = {**params, "Pagina": page, "Cantidad": PAGE_SIZE}
        try:
            items = unwrap(client.get_json(f"{API_BASE}/productos", query))
        except (httpx.HTTPError, ValueError) as error:
            yield FetchedPage(label=label, error=f"{type(error).__name__}: {error}")
            return
        observations = []
        for item in items:
            try:
                observations.append(to_observation(item, city, branch, category, subcategory))
            except HipermaxiApiError as error:
                logger.warning("%s: %s", label, error)
        yield FetchedPage(label=label, observations=observations)
        if len(items) < PAGE_SIZE:
            return
        page += 1


def _flight_chunks(script_text: str) -> Iterator[str]:
    """Decodifica los textos de cada self.__next_f.push([...]) del script."""
    for match in re.finditer(r"self\.__next_f\.push\((\[.*?\])\)", script_text, re.DOTALL):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for part in payload:
            if isinstance(part, str):
                yield part


def _balanced_array(text: str, start: int) -> str | None:
    """Recorta el arreglo JSON que empieza en start, respetando corchetes y comillas."""
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _to_category(item: dict) -> Category:
    """Convierte una categoría del árbol de Next.js."""
    subcategories = tuple(
        Subcategory(int(sub["idSubcategory"]), str(sub["description"]).strip())
        for sub in item.get("subcategories", [])
    )
    return Category(
        category_id=int(item["idCategory"]),
        name=str(item["description"]).strip(),
        rubro=int(item.get("idRubro", 0)),
        subcategories=subcategories,
    )


def _to_decimal(value: object) -> Decimal | None:
    """Convierte un número de la API a Decimal con dos decimales."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value)).quantize(CENT)
    except InvalidOperation:
        return None
