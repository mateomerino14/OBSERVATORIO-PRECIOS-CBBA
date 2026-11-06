from datetime import date
from decimal import Decimal

import psycopg
import pytest

from observatory.db import list_migrations, migrate
from observatory.models import Branch, PriceObservation
from observatory.storage import (
    UnknownChainError,
    finish_run,
    save_observation,
    start_run,
)

pytestmark = pytest.mark.db

BLANCO_GALINDO = Branch(
    code="hipermaxi-blanco-galindo", name="HIPERMAXI BLANCO GALINDO", city="cochabamba"
)
TODAY = date(2026, 11, 6)


def make_observation(**changes: object) -> PriceObservation:
    values = {
        "chain_code": "hipermaxi",
        "branch": BLANCO_GALINDO,
        "external_code": "891816",
        "name": "Arroz Familiar Caisy 1 kg",
        "brand": "Caisy",
        "url": "https://www.hipermaxi.com/cochabamba/hipermaxi-blanco-galindo/producto/891816/x",
        "price": Decimal("16.50"),
        "regular_price": None,
        "available": True,
        "stock": 50,
    }
    values.update(changes)
    return PriceObservation(**values)


def test_migrate_is_idempotent(db: psycopg.Connection) -> None:
    assert migrate(db) == []
    versions = [row[0] for row in db.execute("SELECT version FROM migracion_aplicada")]
    assert versions == [version for version, _ in list_migrations()]


def test_save_observation_stores_product_with_normalized_content(db: psycopg.Connection) -> None:
    save_observation(db, make_observation(), TODAY)

    product = db.execute(
        "SELECT nombre, marca, contenido_cantidad, contenido_unidad FROM producto"
    ).fetchone()
    assert product == ("Arroz Familiar Caisy 1 kg", "Caisy", Decimal(1000), "g")
    observation = db.execute(
        "SELECT fecha, precio, disponible, existencias FROM observacion_precio"
    ).fetchone()
    assert observation == (TODAY, Decimal("16.50"), True, 50)


def test_same_day_keeps_one_row_with_latest_price(db: psycopg.Connection) -> None:
    save_observation(db, make_observation(), TODAY)
    save_observation(db, make_observation(price=Decimal("17.90")), TODAY)

    rows = db.execute("SELECT precio FROM observacion_precio").fetchall()
    assert rows == [(Decimal("17.90"),)]


def test_new_day_adds_history(db: psycopg.Connection) -> None:
    save_observation(db, make_observation(), TODAY)
    save_observation(db, make_observation(price=Decimal("17.90")), date(2026, 11, 7))

    count = db.execute("SELECT count(*) FROM observacion_precio").fetchone()[0]
    products = db.execute("SELECT count(*) FROM producto").fetchone()[0]
    assert (count, products) == (2, 1)


def test_unknown_chain_saves_nothing(db: psycopg.Connection) -> None:
    with pytest.raises(UnknownChainError):
        save_observation(db, make_observation(chain_code="ketal"), TODAY)

    assert db.execute("SELECT count(*) FROM producto").fetchone()[0] == 0


def test_rejects_non_positive_price(db: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        save_observation(db, make_observation(price=Decimal(0)), TODAY)


@pytest.mark.parametrize(
    ("pages_ok", "pages_failed", "expected"),
    [(10, 0, "completada"), (8, 2, "con_errores"), (0, 3, "fallida"), (0, 0, "fallida")],
)
def test_finish_run_sets_status(
    db: psycopg.Connection, pages_ok: int, pages_failed: int, expected: str
) -> None:
    run_id = start_run(db, "hipermaxi")

    assert finish_run(db, run_id, pages_ok, pages_failed) == expected
    stored = db.execute("SELECT estado FROM ejecucion WHERE id = %s", (run_id,)).fetchone()[0]
    assert stored == expected


def test_weight_products_are_stored_per_kilo_with_category(db: psycopg.Connection) -> None:
    weighed = make_observation(
        external_code="414069",
        name="Picaña Especial",
        sold_by_weight=True,
        category="Carnes",
        subcategory="Carne de Res",
    )

    save_observation(db, weighed, TODAY)

    row = db.execute(
        "SELECT contenido_cantidad, contenido_unidad, vendido_por_peso, categoria, subcategoria "
        "FROM producto"
    ).fetchone()
    assert row == (Decimal(1000), "g", True, "Carnes", "Carne de Res")


def test_branch_keeps_external_id_and_address(db: psycopg.Connection) -> None:
    branch = Branch(
        code="hipermaxi-sacaba",
        name="HIPERMAXI SACABA",
        city="cochabamba",
        external_id="48",
        address="Av. Villazón",
    )

    save_observation(db, make_observation(branch=branch), TODAY)

    row = db.execute("SELECT id_externo, direccion FROM sucursal").fetchone()
    assert row == ("48", "Av. Villazón")


def test_all_tables_have_row_level_security(db: psycopg.Connection) -> None:
    rows = db.execute(
        "SELECT relname FROM pg_class WHERE relkind = 'r' "
        "AND relnamespace = 'public'::regnamespace AND NOT relrowsecurity"
    ).fetchall()

    assert rows == []
