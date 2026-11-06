from decimal import Decimal

import pytest

from observatory.models import Branch
from observatory.sources.hipermaxi import (
    PageParseError,
    ProductLocation,
    discover_product_urls,
    parse_product_page,
    parse_product_url,
)

BASE = "https://www.hipermaxi.com"
CAISY_URL = f"{BASE}/cochabamba/hipermaxi-blanco-galindo/producto/891816/arroz-familiar-caisy-1-kg"
POPULAR_URL = (
    f"{BASE}/cochabamba/hipermaxi-blanco-galindo/producto/005788/arroz-popular-hipermaxi-1-kg"
)


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested.append(url)
        return self.pages[url]


def test_parse_product_url_reads_city_branch_and_code() -> None:
    assert parse_product_url(CAISY_URL) == ProductLocation(
        "cochabamba", "hipermaxi-blanco-galindo", "891816"
    )


@pytest.mark.parametrize(
    "url",
    [f"{BASE}/cochabamba/ofertas", f"{BASE}/nosotros", f"{BASE}/cochabamba/x/producto/"],
)
def test_parse_product_url_ignores_other_pages(url: str) -> None:
    assert parse_product_url(url) is None


def test_parse_product_page_reads_full_product(fixture_text) -> None:
    observation = parse_product_page(fixture_text("hipermaxi_producto.html"), CAISY_URL)

    assert observation.chain_code == "hipermaxi"
    assert observation.branch == Branch(
        "hipermaxi-blanco-galindo", "HIPERMAXI BLANCO GALINDO", "cochabamba"
    )
    assert observation.external_code == "891816"
    assert observation.name == "Arroz Familiar Caisy 1 kg"
    assert observation.brand == "Caisy"
    assert observation.price == Decimal("16.50")
    assert observation.regular_price is None
    assert observation.available is True
    assert observation.stock == 50


def test_parse_product_page_handles_graph_list_offers_and_no_stock(fixture_text) -> None:
    observation = parse_product_page(fixture_text("hipermaxi_producto_minimo.html"), POPULAR_URL)

    assert observation.price == Decimal("29.90")
    assert observation.brand == "Hipermaxi"
    assert observation.stock == 0
    assert observation.available is False
    assert observation.branch.name == "HIPERMAXI BLANCO GALINDO"


def test_parse_product_page_keeps_regular_price_only_when_higher(fixture_text) -> None:
    html = fixture_text("hipermaxi_producto.html").replace(
        '"price":16.5', '"price":14,"highPrice":16.5'
    )

    observation = parse_product_page(html, CAISY_URL)

    assert observation.price == Decimal("14.00")
    assert observation.regular_price == Decimal("16.50")


def test_parse_product_page_marks_out_of_stock_from_schema(fixture_text) -> None:
    html = fixture_text("hipermaxi_producto.html").replace("InStock", "OutOfStock")

    assert parse_product_page(html, CAISY_URL).available is False


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<html><body>Sin datos</body></html>", "Sin JSON-LD"),
        (
            '<script type="application/ld+json">{"name":"X","offers":{"price":0}}</script>',
            "Sin precio",
        ),
        ('<script type="application/ld+json">{oops</script>', "Sin JSON-LD"),
    ],
)
def test_parse_product_page_rejects_incomplete_pages(html: str, message: str) -> None:
    with pytest.raises(PageParseError, match=message):
        parse_product_page(html, CAISY_URL)


def test_discover_follows_sitemap_index_and_filters_city(fixture_text) -> None:
    client = FakeClient(
        {
            f"{BASE}/sitemap.xml": fixture_text("hipermaxi_sitemap_indice.xml"),
            f"{BASE}/sitemap-productos-1.xml": fixture_text("hipermaxi_sitemap_productos.xml"),
            f"{BASE}/sitemap-paginas.xml": fixture_text("hipermaxi_sitemap_paginas.xml"),
        }
    )

    urls = list(discover_product_urls(client, "cochabamba"))

    assert urls == [CAISY_URL, POPULAR_URL]
