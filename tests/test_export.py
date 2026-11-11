import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from observatory.basket import load_basket, sync_basket
from observatory.export import (
    build_dashboard,
    market_cost,
    presentation_label,
    to_item_unit,
    write_dashboard,
)
from observatory.models import Branch, PriceObservation
from observatory.sources.bcb import ExchangeRate
from observatory.storage import save_exchange_rates, save_market_prices, save_observations

BASKET = """
codigo = "prueba"
nombre = "Canasta de prueba"
personas = 1
periodo = "semanal"

[[producto]]
codigo = "arroz"
nombre = "Arroz"
categoria = "arroz"
unidad = "g"
cantidad = 920
incluir = ['^arroz\\b']

[[producto]]
codigo = "papaya"
nombre = "Papaya"
categoria = "frutas"
unidad = "g"
cantidad = 1500
peso_unidad = 1500
incluir = ['^papaya\\b']
"""
TODAY = date(2026, 11, 11)
BRANCHES = [
    Branch(code="hipermaxi-blanco-galindo", name="HIPERMAXI BLANCO GALINDO", city="cochabamba"),
    Branch(code="hipermaxi-sacaba", name="HIPERMAXI SACABA", city="cochabamba"),
]


@pytest.fixture
def basket(tmp_path: Path):
    path = tmp_path / "canasta.toml"
    path.write_text(BASKET, encoding="utf-8")
    return load_basket(path)


def observation(branch: Branch, code: str, name: str, price: str) -> PriceObservation:
    return PriceObservation(
        chain_code="hipermaxi",
        branch=branch,
        external_code=code,
        name=name,
        brand=None,
        url=f"https://hipermaxi.com/x/{code}",
        price=Decimal(price),
        regular_price=None,
        available=True,
        stock=None,
    )


def market_row(product: str, month: date, price: str, quantity: str, unit: str) -> dict:
    return {
        "fuente": "defensoria",
        "ciudad": "cochabamba",
        "producto": product,
        "mes": month,
        "precio": Decimal(price),
        "presentacion_cantidad": Decimal(quantity),
        "presentacion_unidad": unit,
        "descripcion": product,
        "informe": month,
        "verificado": True,
        "fuente_url": "https://x",
    }


def test_presentation_label_names_common_sizes() -> None:
    assert presentation_label(Decimal("460.000"), "g") == "1 libra"
    assert presentation_label(Decimal(946), "ml") == "bolsa 946 ml"
    assert presentation_label(Decimal(123), "g") == "123 g"


def test_to_item_unit_converts_pieces_with_unit_weight(basket) -> None:
    papaya = basket.items[1]
    rice = basket.items[0]

    assert to_item_unit(papaya, Decimal(15), "u") == Decimal("0.01")
    assert to_item_unit(rice, Decimal("0.01"), "g") == Decimal("0.01")
    assert to_item_unit(rice, Decimal(1), "u") is None


def test_market_cost_needs_every_requested_item(basket) -> None:
    prices = {"arroz": Decimal("0.015")}

    assert market_cost(basket, prices) is None
    assert market_cost(basket, prices, {"arroz"}) == Decimal("13.800")


@pytest.mark.db
def test_build_dashboard_with_all_sources(db: psycopg.Connection, basket, tmp_path: Path) -> None:
    for branch, price in zip(BRANCHES, ("16.00", "18.00"), strict=True):
        save_observations(db, [observation(branch, "1", "Arroz Caisy 1 kg", price)], TODAY)
    sync_basket(db, basket)
    save_market_prices(
        db,
        [
            market_row("arroz", date(2024, 12, 1), "6.00", "460", "g"),
            market_row("arroz", date(2025, 12, 1), "6.90", "460", "g"),
            market_row("papaya", date(2025, 12, 1), "15.00", "1", "u"),
        ],
    )
    save_exchange_rates(
        db,
        "bcb_oficial",
        [
            ExchangeRate(date(2026, 6, 26), Decimal("6.96"), Decimal("6.86")),
            ExchangeRate(date(2026, 11, 11), Decimal("11.71"), None),
        ],
    )
    save_exchange_rates(db, "paralelo", [ExchangeRate(date(2025, 5, 31), Decimal("16.39"), None)])

    document = build_dashboard(db, basket, "cochabamba")

    assert document["ultimo_dia"] == "2026-11-11"
    assert document["cobertura"]["sucursales"] == 2
    # Canasta de la ciudad: promedio de las dos sucursales (16 y 18 Bs/kg por 920 g).
    assert document["canasta"]["hoy"]["tipico"] == pytest.approx(15.64)
    market = {row["mes"]: row for row in document["canasta_mercado"]["por_mes"]}
    # Diciembre 2025: arroz 6,90 por 2 libras + 1 papaya de Bs 15.
    assert market["2025-12-01"]["total"] == pytest.approx(28.80)
    assert market["2025-12-01"]["comparable"] == pytest.approx(13.80)
    assert market["2024-12-01"]["total"] is None
    assert document["dolar"]["fin_tipo_fijo"]["fecha"] == "2026-06-26"
    assert document["dolar"]["oficial_hoy"]["venta"] == pytest.approx(11.71)
    versus = document["super_vs_mercado"]["productos"]
    assert [row["codigo"] for row in versus] == ["arroz"]
    assert versus[0]["presentacion"] == "1 libra"
    assert versus[0]["super_tipico"] == pytest.approx(7.82)
    risers = document["subidas_mercado"]["productos"]
    assert risers[0]["nombre"] == "Arroz"
    assert risers[0]["variacion_pct"] == pytest.approx(15.0)
    rice = next(product for product in document["productos"] if product["codigo"] == "arroz")
    assert rice["hoy"] == {"tipico": 17.0, "minimo": 16.0, "productos": 2}
    assert rice["tienda"][0]["sucursales"] == 2
    assert len(rice["diario"]) == 2
    suggestions = document["sugerencias"]
    assert suggestions["productos_catalogo"] == 1
    assert {item["codigo"] for item in suggestions["items"]} == {"arroz", "papaya"}
    anomalies = document["anomalias"]
    assert anomalies["mercado"]["items"] == []
    assert anomalies["super"]["dias"] == 1
    assert anomalies["super"]["items"] == []

    path = write_dashboard(document, tmp_path / "datos" / "dashboard.json")
    assert json.loads(path.read_text())["version"] == 1


@pytest.mark.db
def test_build_dashboard_on_empty_database(db: psycopg.Connection, basket) -> None:
    document = build_dashboard(db, basket, "cochabamba")

    assert document["ultimo_dia"] is None
    assert document["canasta"]["hoy"] is None
    assert document["super_vs_mercado"]["productos"] == []
    assert document["subidas_mercado"]["productos"] == []
    assert document["sugerencias"] is None
    assert document["grupos_mercado"] is None
    assert document["anomalias"]["super"] == {
        "fecha": None,
        "dias": 0,
        "minimo_dias": 8,
        "cambio_minimo_pct": 20.0,
        "items": [],
    }


@pytest.mark.db
def test_branches_with_different_coverage_compare_on_common_items(
    db: psycopg.Connection, basket
) -> None:
    rice = [observation(branch, "1", "Arroz Caisy 1 kg", "16.00") for branch in BRANCHES]
    for item in rice:
        save_observations(db, [item], TODAY)
    papaya = PriceObservation(
        **{
            **observation(BRANCHES[1], "2", "Papaya kg", "13.90").__dict__,
            "sold_by_weight": True,
            "subcategory": "Frutas",
        }
    )
    save_observations(db, [papaya], TODAY)
    sync_basket(db, basket)

    document = build_dashboard(db, basket, "cochabamba")

    # La ciudad suma arroz y papaya, aunque solo una sucursal venda papaya.
    assert document["canasta"]["hoy"] == {
        "fecha": "2026-11-11",
        "tipico": pytest.approx(14.72 + 20.85),
        "economico": pytest.approx(14.72 + 20.85),
        "items": 2,
    }
    # Entre sucursales se compara solo el arroz, que tienen las dos.
    branches = {row["sucursal"]: row for row in document["canasta"]["por_sucursal"]}
    assert [row["tipico"] for row in branches.values()] == [pytest.approx(14.72)] * 2
    assert branches["HIPERMAXI SACABA"]["items_sucursal"] == 2
    assert branches["HIPERMAXI BLANCO GALINDO"]["items"] == 1
