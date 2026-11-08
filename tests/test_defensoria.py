from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from observatory.sources.defensoria import (
    PRESENTATIONS,
    DefensoriaParseError,
    identify_product,
    parse_city_table,
    read_csv,
)
from observatory.storage import save_market_prices

PROJECT_CSV = Path(__file__).parents[1] / "fuentes" / "defensoria" / "cochabamba.csv"


def prices_by_key(prices) -> dict[tuple[str, date], Decimal]:
    return {(price.product, price.month): price.price for price in prices}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Arroz de primera/grano de oro", "arroz"),
        ("Leche fluida entera natural", "leche_fluida"),
        ("Leche pasteurizada", "leche_fluida"),
        ("Leche entera en polvo instantánea", "leche_polvo"),
        ("Plátano/postre mediano para cocinar", "platano_cocinar"),
        ("Plátano o banano mediano", "platano"),
        ("Carne de res molida corriente", "res_molida"),
        ("Carne de res pulpa especial", "pulpa_res"),
        ("Mantequilla Zanahoria mediana", "zanahoria"),
        ("gramos Azúcar granulada blanca", "azucar"),
        ("Precios de productos", None),
    ],
)
def test_identify_product_takes_rightmost_name(text: str, expected: str | None) -> None:
    assert identify_product(text) == expected


def test_parses_two_month_table(fixture_text) -> None:
    prices = parse_city_table(fixture_text("defensoria_2025-12.txt"), date(2025, 12, 1))

    values = prices_by_key(prices)
    assert len({price.product for price in prices}) == 21
    assert values[("arroz", date(2025, 11, 1))] == Decimal("7.22")
    assert values[("arroz", date(2025, 12, 1))] == Decimal("7.00")
    assert values[("pollo_entero", date(2025, 12, 1))] == Decimal("18.83")
    assert values[("leche_fluida", date(2025, 12, 1))] == Decimal("9.08")
    assert all(price.report == date(2025, 12, 1) for price in prices)


def test_parses_five_month_table_with_wrapped_names(fixture_text) -> None:
    prices = parse_city_table(fixture_text("defensoria_2025-01.txt"), date(2025, 1, 1))

    values = prices_by_key(prices)
    assert values[("margarina", date(2024, 8, 1))] == Decimal("12.49")
    assert values[("margarina", date(2025, 1, 1))] == Decimal("35.22")
    assert values[("zanahoria", date(2024, 10, 1))] == Decimal("26.71")
    assert values[("papaya", date(2024, 12, 1))] == Decimal("8.60")
    months = {price.month for price in prices}
    assert months == {date(2024, m, 1) for m in (8, 10, 11, 12)} | {date(2025, 1, 1)}


def test_stops_at_the_end_of_the_city_table(fixture_text) -> None:
    prices = parse_city_table(fixture_text("defensoria_2025-03.txt"), date(2025, 3, 1))

    values = prices_by_key(prices)
    assert len(prices) == 42
    # La tabla siguiente (Sucre) tiene otro precio de arroz; no debe colarse.
    assert values[("arroz", date(2025, 3, 1))] == Decimal("6.34")


def test_variation_against_first_column_counts_as_verified(fixture_text) -> None:
    prices = parse_city_table(fixture_text("defensoria_2024-11.txt"), date(2024, 11, 1))

    rice = [price for price in prices if price.product == "arroz"]
    assert {price.month for price in rice} == {date(2024, m, 1) for m in (8, 10, 11)}
    assert all(price.verified for price in rice)


def test_fails_without_city_table() -> None:
    with pytest.raises(DefensoriaParseError, match="tabla"):
        parse_city_table("TABLA 3. PRECIOS DE PRODUCTOS LA PAZ\n", date(2025, 1, 1))


def test_project_csv_covers_16_months_and_known_products() -> None:
    rows = read_csv(PROJECT_CSV, "cochabamba")

    months = {row["mes"] for row in rows}
    assert min(months) == date(2024, 8, 1)
    assert max(months) == date(2025, 12, 1)
    assert len(months) == 16
    assert {row["producto"] for row in rows} == set(PRESENTATIONS)


def test_project_csv_reproduces_published_basket_cost() -> None:
    rows = read_csv(PROJECT_CSV, "cochabamba")
    price = {(row["producto"], row["mes"]): row["precio"] for row in rows}
    quantities = {
        "papaya": Decimal(1),
        "tomate": Decimal(2),
        "azucar": Decimal(1),
        "arroz": Decimal(2),
        "harina_trigo": Decimal(2),
        "fideo": Decimal(1),
        "pulpa_res": Decimal(1),
        "pollo_entero": Decimal(2),
        "leche_fluida": Decimal(1),
        "huevos": Decimal(10),
    }

    def basket(month: date) -> Decimal:
        total = sum(price[(code, month)] * amount for code, amount in quantities.items())
        total += price[("platano", month)] / 25 * 12
        # 2 libras de cebolla y de zanahoria; la cuartilla equivale a 6 libras.
        total += (price[("cebolla", month)] + price[("zanahoria", month)]) * 2 / 6
        return total

    # La Defensoría publicó Bs 171 (enero) y Bs 247 (diciembre de 2025).
    assert abs(basket(date(2025, 1, 1)) - 171) < 1
    assert abs(basket(date(2025, 12, 1)) - 247) < 1


def test_read_csv_rejects_unknown_products(tmp_path: Path) -> None:
    broken = tmp_path / "mal.csv"
    header = PROJECT_CSV.read_text(encoding="utf-8").splitlines()[0]
    broken.write_text(
        header + "\n2025-01,quinua,10,460,g,Quinua,2025-01,true,https://x\n", encoding="utf-8"
    )

    with pytest.raises(DefensoriaParseError, match="quinua"):
        read_csv(broken, "cochabamba")


@pytest.mark.db
def test_import_is_idempotent_and_view_gives_unit_price(db: psycopg.Connection) -> None:
    rows = read_csv(PROJECT_CSV, "cochabamba")

    save_market_prices(db, rows)
    save_market_prices(db, rows)

    assert db.execute("SELECT count(*) FROM precio_mercado").fetchone()[0] == len(rows)
    unit_price = db.execute(
        "SELECT round(precio_unitario, 5), unidad FROM precio_mercado_unitario "
        "WHERE producto = 'arroz' AND mes = '2025-12-01'"
    ).fetchone()
    assert unit_price == (round(Decimal("7.00") / 460, 5), "g")
