import json
from decimal import Decimal

import httpx
import pytest

from observatory.http_client import BotProtectionError
from observatory.models import Branch
from observatory.sources.hipermaxi import (
    API_BASE,
    PAGE_SIZE,
    SITE_BASE,
    HipermaxiApiError,
    iter_pages,
    list_branches,
    parse_category_tree,
    slugify,
    to_observation,
    unwrap,
)

BLANCO_GALINDO = Branch(
    code="hipermaxi-blanco-galindo",
    name="HIPERMAXI BLANCO GALINDO",
    city="cochabamba",
    external_id="40",
    address="A.BORDA #2029",
)


def product(**changes: object) -> dict:
    values = {
        "IdProducto": "414069",
        "Descripcion": "Mayonesa Kris 980 ml",
        "PrecioVenta": 40.5,
        "UnidadMedida": "PCE",
        "Stock": 375,
        "ConOferta": False,
        "PrecioOferta": 0,
        "PrecioOriginal": 0,
        "VerStock": True,
        "ControlStock": True,
    }
    values.update(changes)
    return values


def api_page(items: list[dict]) -> dict:
    return {"ConError": False, "Estado": 200, "Mensaje": None, "Dato": items}


class FakeClient:
    """Responde según la ruta y los parámetros, y anota cada pedido."""

    def __init__(self, fixture_text, products_by_query=None, tree_html=None) -> None:
        self.fixture_text = fixture_text
        self.products_by_query = products_by_query or {}
        self.tree_html = tree_html
        self.requests: list[tuple[str, dict | None]] = []

    def get_json(self, url: str, params: dict | None = None) -> object:
        self.requests.append((url, params))
        if url.endswith("/markets/ciudades"):
            return json.loads(self.fixture_text("hipermaxi_api_ciudades.json"))
        if url.endswith("/markets/activos"):
            return json.loads(self.fixture_text("hipermaxi_api_sucursales.json"))
        key = (params["IdLocatario"], params.get("IdsSubcategoria"), params["Pagina"])
        response = self.products_by_query.get(key, api_page([]))
        if isinstance(response, Exception):
            raise response
        return response

    def get_text(self, url: str) -> str:
        self.requests.append((url, None))
        if self.tree_html is None:
            raise httpx.ConnectError("sin conexión")
        return self.tree_html


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Arroz Familiar Caisy 1 kg", "arroz-familiar-caisy-1-kg"),
        ("Picaña Especial kg", "picana-especial-kg"),
        ("HIPERMAXI CIRCUNVALACIÓN", "hipermaxi-circunvalacion"),
        ("Leche  Pil (UHT) 900ml", "leche-pil-uht-900ml"),
    ],
)
def test_slugify_matches_store_urls(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_unwrap_rejects_api_errors() -> None:
    with pytest.raises(HipermaxiApiError, match="error"):
        unwrap({"ConError": True, "Estado": 400, "Mensaje": "Parámetros inválidos"})


def test_list_branches_keeps_only_cochabamba_supermarkets(fixture_text) -> None:
    branches = list_branches(FakeClient(fixture_text), "cochabamba")

    assert [item.branch.name for item in branches] == [
        "HIPERMAXI BLANCO GALINDO",
        "HIPERMAXI JUAN DE LA ROSA",
        "HIPERMAXI SACABA",
        "HIPERMAXI CIRCUNVALACION",
        "HIPERMAXI PANAMERICANA",
    ]
    assert branches[0].branch == BLANCO_GALINDO
    panamericana = branches[-1]
    assert (panamericana.market_id, panamericana.branch_id) == (654, 43)


def test_list_branches_fails_for_unknown_city(fixture_text) -> None:
    with pytest.raises(HipermaxiApiError, match="no atiende"):
        list_branches(FakeClient(fixture_text), "tarija")


def test_parse_category_tree_from_real_page(fixture_text) -> None:
    categories = parse_category_tree(fixture_text("hipermaxi_categoria.html"))

    assert len(categories) == 19
    abarrotes = categories[0]
    assert (abarrotes.category_id, abarrotes.name, abarrotes.rubro) == (1, "Abarrotes", 1)
    assert abarrotes.subcategories[0].name == "Aderezos"
    assert sum(len(item.subcategories) for item in categories) == 145


def test_parse_category_tree_fails_without_tree() -> None:
    with pytest.raises(HipermaxiApiError, match="árbol"):
        parse_category_tree("<html><body><script>console.log(1)</script></body></html>")


def test_to_observation_from_real_api_item(fixture_text) -> None:
    item = json.loads(fixture_text("hipermaxi_api_productos.json"))["Dato"][0]

    observation = to_observation(item, "cochabamba", BLANCO_GALINDO, "Abarrotes", "Aderezos")

    assert observation.name == "Mayonesa Kris 980 ml"
    assert observation.price == Decimal("40.50")
    assert observation.regular_price is None
    assert observation.stock == 375
    assert observation.available is True
    assert observation.sold_by_weight is False
    assert (observation.category, observation.subcategory) == ("Abarrotes", "Aderezos")
    assert observation.url == (
        f"{SITE_BASE}/cochabamba/hipermaxi-blanco-galindo/producto/"
        f"{item['IdProducto']}/mayonesa-kris-980-ml"
    )


def test_to_observation_uses_offer_and_keeps_regular_price() -> None:
    item = product(ConOferta=True, PrecioOferta=34.9, PrecioOriginal=40.5)

    observation = to_observation(item, "cochabamba", BLANCO_GALINDO, None, None)

    assert observation.price == Decimal("34.90")
    assert observation.regular_price == Decimal("40.50")


def test_to_observation_ignores_offer_that_is_not_lower() -> None:
    observation = to_observation(
        product(ConOferta=True, PrecioOferta=45), "cochabamba", BLANCO_GALINDO, None, None
    )

    assert (observation.price, observation.regular_price) == (Decimal("40.50"), None)


def test_to_observation_handles_weight_items_with_negative_stock() -> None:
    item = product(
        Descripcion="Picaña Especial kg",
        UnidadMedida="KGM",
        Stock=-354.745,
        VerStock=False,
        ControlStock=False,
    )

    observation = to_observation(item, "cochabamba", BLANCO_GALINDO, None, None)

    assert observation.sold_by_weight is True
    assert observation.stock is None
    assert observation.available is True


def test_to_observation_marks_controlled_items_without_stock_unavailable() -> None:
    observation = to_observation(product(Stock=0), "cochabamba", BLANCO_GALINDO, None, None)

    assert observation.available is False


@pytest.mark.parametrize("changes", [{"PrecioVenta": 0}, {"Descripcion": ""}, {"IdProducto": None}])
def test_to_observation_rejects_incomplete_items(changes: dict) -> None:
    with pytest.raises(HipermaxiApiError):
        to_observation(product(**changes), "cochabamba", BLANCO_GALINDO, None, None)


def test_iter_pages_walks_subcategories_and_pages(fixture_text) -> None:
    full_page = api_page([product(IdProducto=str(number)) for number in range(PAGE_SIZE)])
    client = FakeClient(
        fixture_text,
        products_by_query={
            (40, 4, 1): full_page,
            (40, 4, 2): api_page([product(IdProducto="extra")]),
        },
        tree_html=fixture_text("hipermaxi_categoria.html"),
    )

    pages = list(iter_pages(client, "cochabamba"))

    first, second = pages[0], pages[1]
    assert first.label == "HIPERMAXI BLANCO GALINDO / Aderezos / página 1"
    assert len(first.observations) == PAGE_SIZE
    assert first.observations[0].subcategory == "Aderezos"
    assert second.label == "HIPERMAXI BLANCO GALINDO / Aderezos / página 2"
    assert len(second.observations) == 1
    product_queries = [params for url, params in client.requests if url == f"{API_BASE}/productos"]
    assert all(params["Cantidad"] == PAGE_SIZE for params in product_queries)


def test_iter_pages_skips_non_canasta_rubros(fixture_text) -> None:
    client = FakeClient(fixture_text, tree_html=fixture_text("hipermaxi_categoria.html"))
    tree = parse_category_tree(fixture_text("hipermaxi_categoria.html"))
    excluded = {sub.subcategory_id for cat in tree if cat.rubro == 4 for sub in cat.subcategories}

    list(iter_pages(client, "cochabamba"))

    requested = {
        params["IdsSubcategoria"]
        for url, params in client.requests
        if url == f"{API_BASE}/productos"
    }
    assert requested
    assert not requested & excluded


def test_iter_pages_without_tree_walks_full_catalog(fixture_text) -> None:
    client = FakeClient(fixture_text, products_by_query={(40, None, 1): api_page([product()])})

    pages = list(iter_pages(client, "cochabamba"))

    assert len(pages) == 5
    assert pages[0].observations[0].category is None
    assert pages[0].label == "HIPERMAXI BLANCO GALINDO / catálogo / página 1"


def test_iter_pages_reports_page_errors_and_continues(fixture_text) -> None:
    request = httpx.Request("GET", API_BASE)
    error = httpx.HTTPStatusError("500", request=request, response=httpx.Response(500))
    client = FakeClient(fixture_text, products_by_query={(40, None, 1): error})

    pages = list(iter_pages(client, "cochabamba"))

    assert pages[0].error.startswith("HTTPStatusError")
    assert all(page.error is None for page in pages[1:])


def test_iter_pages_stops_on_bot_protection(fixture_text) -> None:
    client = FakeClient(
        fixture_text, products_by_query={(40, None, 1): BotProtectionError("verificación")}
    )

    with pytest.raises(BotProtectionError):
        list(iter_pages(client, "cochabamba"))
