"""Fuente Hipermaxi: descubre productos por sitemap y lee el precio del JSON-LD de cada página."""

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from observatory.models import Branch, PriceObservation

CHAIN_CODE = "hipermaxi"
BASE_URL = "https://www.hipermaxi.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
MAX_SITEMAP_DEPTH = 3

# Ruta de producto: /<ciudad>/<sucursal>/producto/<código>/<slug>
PRODUCT_PATH = re.compile(
    r"^/(?P<city>[a-z-]+)/(?P<branch>[a-z0-9-]+)/producto/(?P<code>[0-9A-Za-z]+)/[^/?#]+/?$"
)
BRANCH_NAME_PATTERN = re.compile(r"al mejor precio en Hipermaxi\s+(?P<name>[^.]+)\.")
STOCK_PATTERN = re.compile(r"Disponibilidad\W*:?\W*\+?(?P<units>\d+)\s+unidad", re.IGNORECASE)
OUT_OF_STOCK_MARKERS = ("outofstock", "soldout", "discontinued")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductLocation:
    """Ciudad, sucursal y código del producto, leídos de la URL."""

    city: str
    branch_code: str
    external_code: str


class PageParseError(ValueError):
    """La página no trae los datos mínimos de un producto."""


def parse_product_url(url: str) -> ProductLocation | None:
    """Lee ciudad, sucursal y código de una URL de producto; None si no es de producto."""
    path = re.sub(r"^https?://[^/]+", "", url)
    match = PRODUCT_PATH.match(path)
    if match is None:
        return None
    return ProductLocation(match["city"], match["branch"], match["code"])


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """Separa un sitemap en (sitemaps hijos, URLs de páginas)."""
    root = ElementTree.fromstring(xml_text)
    locations = [node.text.strip() for node in root.iter(f"{SITEMAP_NAMESPACE}loc") if node.text]
    if root.tag == f"{SITEMAP_NAMESPACE}sitemapindex":
        return locations, []
    return [], locations


def discover_product_urls(client, city: str, sitemap_url: str = SITEMAP_URL) -> Iterator[str]:
    """Recorre el sitemap y entrega las URLs de producto de una ciudad, sin repetir."""
    pending = [(sitemap_url, 0)]
    seen: set[str] = set()
    while pending:
        current, depth = pending.pop(0)
        children, pages = parse_sitemap(client.get_text(current))
        if depth < MAX_SITEMAP_DEPTH:
            pending.extend((child, depth + 1) for child in children)
        for page in pages:
            location = parse_product_url(page)
            if location is None or location.city != city or page in seen:
                continue
            seen.add(page)
            yield page


def parse_product_page(html: str, url: str) -> PriceObservation:
    """Arma la observación de precio a partir del HTML de una página de producto."""
    location = parse_product_url(url)
    if location is None:
        raise PageParseError(f"No es una URL de producto: {url}")
    tree = HTMLParser(html)
    product = _find_product_json_ld(tree)
    if product is None:
        raise PageParseError(f"Sin JSON-LD de producto: {url}")
    offer = _first_offer(product.get("offers"))
    price = _to_decimal(offer.get("price") or offer.get("lowPrice"))
    if price is None or price <= 0:
        raise PageParseError(f"Sin precio válido: {url}")
    name = str(product.get("name") or "").strip()
    if not name:
        raise PageParseError(f"Sin nombre: {url}")

    page_text = tree.body.text(separator=" ") if tree.body else ""
    stock = _parse_stock(page_text)
    branch = Branch(
        code=location.branch_code,
        name=_parse_branch_name(tree, location.branch_code),
        city=location.city,
    )
    return PriceObservation(
        chain_code=CHAIN_CODE,
        branch=branch,
        external_code=location.external_code,
        name=name,
        brand=_parse_brand(product.get("brand")),
        url=url,
        price=price,
        regular_price=_regular_price(offer, price),
        available=_is_available(offer, stock),
        stock=stock,
    )


def _find_product_json_ld(tree: HTMLParser) -> dict | None:
    """Busca entre los bloques JSON-LD el objeto que describe el producto con su oferta."""
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text())
        except json.JSONDecodeError:
            continue
        for candidate in _walk_json_ld(data):
            if "offers" in candidate and "name" in candidate:
                return candidate
    return None


def _walk_json_ld(data: object) -> Iterator[dict]:
    """Recorre listas y @graph del JSON-LD entregando cada objeto."""
    if isinstance(data, list):
        for item in data:
            yield from _walk_json_ld(item)
        return
    if isinstance(data, dict):
        yield data
        yield from _walk_json_ld(data.get("@graph", []))


def _first_offer(offers: object) -> dict:
    """Normaliza offers, que puede venir como objeto o como lista."""
    if isinstance(offers, list) and offers:
        return offers[0]
    if isinstance(offers, dict):
        return offers
    return {}


def _to_decimal(value: object) -> Decimal | None:
    """Convierte un precio de JSON a Decimal con dos decimales."""
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _regular_price(offer: dict, price: Decimal) -> Decimal | None:
    """Precio antes del descuento, solo si es mayor al precio actual."""
    regular = _to_decimal(offer.get("highPrice"))
    if regular is not None and regular > price:
        return regular
    return None


def _parse_brand(brand: object) -> str | None:
    """La marca puede venir como texto o como objeto con name."""
    if isinstance(brand, dict):
        brand = brand.get("name")
    if isinstance(brand, str) and brand.strip():
        return brand.strip()
    return None


def _parse_stock(page_text: str) -> int | None:
    """Lee 'Disponibilidad: 29 unidades'; '+50' se guarda como 50."""
    match = STOCK_PATTERN.search(page_text)
    if match is None:
        return None
    return int(match["units"])


def _is_available(offer: dict, stock: int | None) -> bool:
    """Disponible según schema.org; si no lo indica, según las unidades visibles."""
    availability = str(offer.get("availability", "")).lower()
    if any(marker in availability for marker in OUT_OF_STOCK_MARKERS):
        return False
    if "instock" in availability:
        return True
    if stock is not None:
        return stock > 0
    return True


def _parse_branch_name(tree: HTMLParser, branch_code: str) -> str:
    """Toma el nombre de la sucursal de la descripción; si no está, lo arma desde la URL."""
    meta = tree.css_first('meta[name="description"]')
    description = ""
    if meta is not None:
        description = meta.attributes.get("content") or ""
    match = BRANCH_NAME_PATTERN.search(description)
    if match is not None:
        return match["name"].strip()
    return branch_code.replace("-", " ").upper()
