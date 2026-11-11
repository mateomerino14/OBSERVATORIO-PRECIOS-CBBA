from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from observatory.basket import load_basket
from observatory.suggest import (
    DEFAULT_THRESHOLD,
    MIN_THRESHOLD,
    REASON_ACCEPTED,
    REASON_EXCLUDED,
    REASON_NAME,
    REASON_PRESENTATION,
    REASON_SUBCATEGORY,
    CatalogProduct,
    clean_name,
    item_threshold,
    leave_one_out_scores,
    rejection_reason,
    suggest,
    vectorize,
)

BASKET = """
codigo = "prueba"
nombre = "Canasta de prueba"
personas = 1
periodo = "semanal"

[[producto]]
codigo = "huevos"
nombre = "Huevos de gallina"
categoria = "huevos"
unidad = "u"
cantidad = 10
subcategorias = ["Huevos"]
incluir = ['^huevos?\\b']
excluir = ['codorniz']

[[producto]]
codigo = "arroz"
nombre = "Arroz de primera"
categoria = "arroz"
unidad = "g"
cantidad = 920
subcategorias = ["Básicos"]
contenido_min = 400
contenido_max = 5000
incluir = ['^arroz\\b']
excluir = ['integral']
"""


@pytest.fixture
def basket(tmp_path: Path):
    path = tmp_path / "prueba.toml"
    path.write_text(BASKET)
    return load_basket(path)


def product(
    product_id: int,
    name: str,
    subcategory: str,
    unit: str,
    code: str | None = None,
    content: str = "1000",
) -> CatalogProduct:
    return CatalogProduct(
        product_id=product_id,
        name=name,
        subcategory=subcategory,
        content=Decimal(content),
        unit=unit,
        url=f"https://example.com/{product_id}",
        item_code=code,
    )


def catalog() -> list[CatalogProduct]:
    eggs = [
        product(1, "Huevo Sofia Mediano 12 un", "Huevos", "u", "huevos", "12"),
        product(2, "Huevos Rolon Mediano 30 un", "Huevos", "u", "huevos", "30"),
        product(3, "Huevo Nido de Oro Mediano 6 un", "Huevos", "u", "huevos", "6"),
        product(4, "Huevos Sofia Grande 15 un", "Huevos", "u", "huevos", "15"),
        product(5, "Huevo Rolon Mediano 20 un", "Huevos", "u", "huevos", "20"),
        product(6, "Huevos de Codorniz Sofia 24 un", "Huevos", "u", None, "24"),
        product(7, "Pack Huevo Sofia Mediano 12 un", "Huevos", "u", None, "12"),
    ]
    rice = [
        product(10, "Arroz Grano de Oro Primera 1 kg", "Básicos", "g", "arroz"),
        product(11, "Arroz Caisy Primera 5 kg", "Básicos", "g", "arroz", "5000"),
        product(12, "Arroz Norte Primera 1 kg", "Básicos", "g", "arroz"),
        product(13, "Arroz Estaquilla Hipermaxi 1 kg", "Fraccionados Hipermaxi", "g"),
        product(14, "Arroz Integral Caisy 1 kg", "Básicos", "g"),
        product(15, "Arroz Grano de Oro Primera 25 kg", "Básicos", "g", None, "25000"),
    ]
    others = [
        product(20, "Galleta Mabel Chocolate 100 gr", "Galletas", "g", None, "100"),
        product(21, "Fideo Don Vittorio Corto 400 gr", "Básicos", "g", None, "400"),
        product(22, "Gaseosa Coca Cola 2 lt", "Gaseosas", "ml", None, "2000"),
        product(23, "Snack Papas Fritas 150 gr", "Snack", "g", None, "150"),
    ]
    return eggs + rice + others


def test_clean_name_drops_quantities_and_packaging() -> None:
    assert clean_name("Arroz Caisy Primera Bolsa 5 KG") == "arroz caisy primera"
    assert clean_name("Leche Pil Natural 946ml") == "leche pil natural"
    assert clean_name("Huevo Sofía 12 un") == "huevo sofia"
    assert clean_name(None) == ""


def test_rejection_reason_names_the_first_failing_rule(basket) -> None:
    rice = basket.items[1]
    products = {item.product_id: item for item in catalog()}
    assert rejection_reason(rice, products[10]) == REASON_ACCEPTED
    assert rejection_reason(rice, products[21]) == REASON_NAME
    assert rejection_reason(rice, products[14]) == REASON_EXCLUDED
    assert rejection_reason(rice, products[13]) == REASON_SUBCATEGORY
    assert rejection_reason(rice, products[15]) == REASON_PRESENTATION


def test_vectors_are_unit_length_and_share_one_space(basket) -> None:
    products = catalog()
    vectors, items = vectorize(basket, products)
    assert vectors.shape[0] == len(products)
    assert items.shape == (len(basket.items), vectors.shape[1])
    norms = np.sqrt(np.asarray(vectors.multiply(vectors).sum(axis=1))).ravel()
    assert norms == pytest.approx(np.ones(len(products)))


def test_leave_one_out_needs_two_products(basket) -> None:
    vectors, _ = vectorize(basket, catalog())
    assert len(leave_one_out_scores(vectors, [0])) == 0
    scores = leave_one_out_scores(vectors, [0, 1, 2])
    assert len(scores) == 3
    assert all(0 < score <= 1 for score in scores)


def test_item_threshold_uses_own_data_with_a_floor() -> None:
    assert item_threshold(np.array([0.9, 0.8])) == DEFAULT_THRESHOLD
    assert item_threshold(np.array([0.2, 0.2, 0.3, 0.2])) == MIN_THRESHOLD
    assert item_threshold(np.array([0.6, 0.7, 0.8, 0.9, 0.95])) == pytest.approx(0.64)


def test_suggest_finds_missed_products_and_skips_deliberate_exclusions(basket) -> None:
    report = suggest(basket, catalog())
    by_code = {item.code: item for item in report.items}

    eggs = by_code["huevos"]
    assert eggs.matched == 5
    suggested = {candidate.product.product_id: candidate for candidate in eggs.candidates}
    # El pack no empieza con "huevo", así que la regla lo deja fuera; el modelo lo encuentra.
    assert suggested[7].reason == REASON_NAME
    # Codorniz está excluido a propósito: no se sugiere aunque se parezca.
    assert 6 not in suggested
    # Solo se sugieren productos con la misma unidad que el ítem.
    assert all(candidate.product.unit == "u" for candidate in eggs.candidates)

    rice_ids = {candidate.product.product_id for candidate in by_code["arroz"].candidates}
    assert 14 not in rice_ids
    assert 20 not in rice_ids


def test_suggest_flags_accepted_products_unlike_the_rest(basket) -> None:
    powder = product(8, "Huevina Polvo Instantaneo 10 u", "Huevos", "u", "huevos", "10")
    products = [*catalog(), powder]
    eggs = next(item for item in suggest(basket, products).items if item.code == "huevos")
    assert eggs.matched == 6
    assert eggs.doubtful
    assert eggs.doubtful[0].product.product_id == 8


def test_evaluation_counts_each_accepted_product(basket) -> None:
    evaluation = suggest(basket, catalog()).evaluation
    # 5 huevos + 3 arroz aceptados.
    assert evaluation.cases == 8
    assert 0 <= evaluation.found_in_top <= evaluation.cases
    assert evaluation.median_rank is not None
    assert evaluation.median_rank >= 1


def test_item_without_matches_uses_its_name(basket) -> None:
    products = [replace_code(item, None) for item in catalog()]
    report = suggest(basket, products)
    rice = next(item for item in report.items if item.code == "arroz")
    assert rice.matched == 0
    assert rice.threshold == DEFAULT_THRESHOLD
    assert report.evaluation.cases == 0
    assert report.evaluation.median_rank is None


def replace_code(item: CatalogProduct, code: str | None) -> CatalogProduct:
    return CatalogProduct(
        item.product_id, item.name, item.subcategory, item.content, item.unit, item.url, code
    )


def test_tied_candidates_keep_a_stable_order(basket) -> None:
    twins = [
        product(31, "Pack Huevo Sofia Mediano 12 un", "Huevos", "u", None, "12"),
        product(30, "Pack Huevo Sofia Mediano 12 un", "Huevos", "u", None, "12"),
    ]
    products = [item for item in catalog() if item.product_id != 7]
    forward = suggest(basket, [*products, *twins]).items[0]
    backward = suggest(basket, [*products, *reversed(twins)]).items[0]
    ids = [candidate.product.product_id for candidate in forward.candidates]
    assert ids[:2] == [30, 31]
    assert ids == [candidate.product.product_id for candidate in backward.candidates]
