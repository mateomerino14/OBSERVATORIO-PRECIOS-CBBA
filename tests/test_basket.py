from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from observatory.basket import (
    BasketDefinitionError,
    StoreProduct,
    assign,
    load_basket,
    matches,
    normalize,
    sync_basket,
)
from observatory.models import Branch, PriceObservation
from observatory.storage import save_observations

BASKET_FILE = Path(__file__).parents[1] / "canastas" / "defensoria_semanal.toml"
TODAY = date(2026, 11, 8)
BRANCH = Branch(code="hipermaxi-blanco-galindo", name="HIPERMAXI BLANCO GALINDO", city="cochabamba")

MINIMAL = """
codigo = "prueba"
nombre = "Canasta de prueba"
personas = 1
periodo = "semanal"

[[producto]]
codigo = "arroz"
nombre = "Arroz"
categoria = "arroz"
unidad = "g"
cantidad = 1000
subcategorias = ["Básicos"]
contenido_max = 5000
incluir = ['^arroz\\b']
excluir = ['integral']

[[producto]]
codigo = "grano"
nombre = "Cualquier grano"
categoria = "granos"
unidad = "g"
cantidad = 500
incluir = ['arroz', 'quinua']
"""


def store_product(name: str, **changes: object) -> StoreProduct:
    values = {
        "product_id": 1,
        "name": name,
        "subcategory": "Básicos",
        "content": Decimal(1000),
        "unit": "g",
    }
    values.update(changes)
    return StoreProduct(**values)


def write_basket(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "canasta.toml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def minimal_basket(tmp_path: Path):
    return load_basket(write_basket(tmp_path, MINIMAL))


def test_normalize_removes_accents_and_case() -> None:
    assert normalize("Azúcar BLANCA Piña") == "azucar blanca pina"


def test_project_basket_file_is_valid() -> None:
    basket = load_basket(BASKET_FILE)

    assert basket.code == "defensoria_semanal"
    assert (basket.people, basket.period, len(basket.items)) == (4, "semanal", 13)
    quantities = {item.code: item.quantity for item in basket.items}
    assert quantities["arroz"] == Decimal(920)
    assert quantities["huevos"] == Decimal(10)


@pytest.mark.parametrize(
    ("product", "expected"),
    [
        (store_product("Arroz Caisy Especial 1 kg"), True),
        (store_product("ARROZ NORTE TIPO 1 5 KG", content=Decimal(5000)), True),
        (store_product("Arroz Integral Caisy 1 kg"), False),
        (store_product("Arroz Caisy 11.34 kg", content=Decimal(11340)), False),
        (store_product("Arroz Caisy 1 kg", subcategory="Snack"), False),
        (store_product("Arroz Caisy 1 kg", unit="ml"), False),
        (store_product("Arroz Caisy", content=None), False),
        (store_product("Galletas de arroz 100 gr", content=Decimal(100)), False),
    ],
)
def test_matches_applies_all_rules(minimal_basket, product: StoreProduct, expected: bool) -> None:
    assert matches(minimal_basket.items[0], product) is expected


def test_assign_gives_product_to_first_item_in_file(minimal_basket) -> None:
    products = [
        store_product("Arroz Caisy 1 kg", product_id=1),
        store_product("Quinua Real 1 kg", product_id=2),
        store_product("Fideo 1 kg", product_id=3),
    ]

    assert assign(minimal_basket, products) == {1: "arroz", 2: "grano"}


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        (MINIMAL.replace('unidad = "g"', 'unidad = "kg"', 1), "unidad"),
        (MINIMAL.replace("incluir = ['^arroz\\b']", "incluir = []"), "incluir"),
        (MINIMAL.replace("incluir = ['^arroz\\b']", "incluir = ['(']"), "expresión"),
        (MINIMAL.replace('periodo = "semanal"', 'periodo = "diario"'), "periodo"),
        (MINIMAL.replace('codigo = "grano"', 'codigo = "arroz"'), "repetidos"),
        (MINIMAL.replace("personas = 1\n", ""), "personas"),
    ],
)
def test_load_basket_rejects_invalid_definitions(tmp_path: Path, broken: str, message: str) -> None:
    with pytest.raises(BasketDefinitionError, match=message):
        load_basket(write_basket(tmp_path, broken))


def observation(code: str, name: str, price: str, subcategory: str = "Básicos") -> PriceObservation:
    return PriceObservation(
        chain_code="hipermaxi",
        branch=BRANCH,
        external_code=code,
        name=name,
        brand=None,
        url=f"https://hipermaxi.com/x/{code}",
        price=Decimal(price),
        regular_price=None,
        available=True,
        stock=None,
        subcategory=subcategory,
    )


@pytest.mark.db
def test_sync_basket_matches_products_and_computes_daily_cost(
    db: psycopg.Connection, minimal_basket
) -> None:
    save_observations(
        db,
        [
            observation("1", "Arroz Caisy 1 kg", "16.00"),
            observation("2", "Arroz Norte 5 kg", "70.00"),
            observation("3", "Arroz Grano de Oro 1 kg", "20.00"),
            observation("4", "Quinua Real 500 gr", "15.00"),
            observation("5", "Arroz Integral 1 kg", "25.00"),
        ],
        TODAY,
    )

    counts = sync_basket(db, minimal_basket)

    assert counts == {"arroz": 3, "grano": 2}
    cost = db.execute(
        "SELECT costo_tipico, costo_economico, items_con_precio, items_total "
        "FROM costo_canasta_diario WHERE canasta = 'prueba'"
    ).fetchone()
    # arroz: 1000 g, mediana 0,016 Bs/g y mínimo 0,014 Bs/g
    # grano: 500 g, integral 0,025 y quinua 0,030 Bs/g -> mediana 0,0275, mínimo 0,025
    assert cost == (Decimal("29.75"), Decimal("26.50"), 2, 2)


@pytest.mark.db
def test_sync_basket_keeps_manual_matches_and_is_idempotent(
    db: psycopg.Connection, minimal_basket
) -> None:
    save_observations(db, [observation("1", "Arroz Caisy 1 kg", "16.00")], TODAY)
    sync_basket(db, minimal_basket)
    with db.transaction():
        db.execute(
            "UPDATE emparejamiento SET metodo = 'manual', producto_canonico_id = "
            "(SELECT id FROM producto_canonico WHERE codigo = 'grano')"
        )

    counts = sync_basket(db, minimal_basket)
    sync_basket(db, minimal_basket)

    assert counts == {"arroz": 0, "grano": 0}
    rows = db.execute(
        "SELECT pc.codigo, e.metodo FROM emparejamiento e "
        "JOIN producto_canonico pc ON pc.id = e.producto_canonico_id"
    ).fetchall()
    assert rows == [("grano", "manual")]
    assert db.execute("SELECT count(*) FROM canasta_item").fetchone()[0] == 2


@pytest.mark.db
def test_unavailable_products_do_not_count_in_cost(db: psycopg.Connection, minimal_basket) -> None:
    sold_out = PriceObservation(
        **{**observation("1", "Arroz Caisy 1 kg", "16.00").__dict__, "available": False}
    )
    save_observations(db, [sold_out], TODAY)

    sync_basket(db, minimal_basket)

    assert db.execute("SELECT count(*) FROM costo_canasta_diario").fetchone()[0] == 0
