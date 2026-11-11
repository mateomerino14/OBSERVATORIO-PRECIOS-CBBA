"""Sugerencias de emparejamiento por similitud de texto (TF-IDF), para revisar las reglas.

Las reglas de la canasta deciden qué producto de tienda cuenta para cada ítem. Este módulo no
las reemplaza: busca productos que se parecen a los que las reglas ya aceptan y explica por qué
las reglas los dejaron fuera. Una persona revisa la lista y, si corresponde, ajusta el TOML.

El modelo:
- Cada nombre se limpia (sin tildes, cantidades ni palabras de presentación) y se representa con
  TF-IDF de n-gramas de 3 a 5 caracteres, que tolera abreviaturas y errores ("Fideos", "FIDEO").
  La subcategoría de la tienda entra con poco peso.
- Cada ítem tiene un prototipo: el promedio de los productos que las reglas aceptan. Sin
  productos aceptados, el prototipo es el nombre del ítem.
- El umbral de cada ítem sale de sus propios datos: el percentil 10 de la similitud de cada
  producto aceptado con el prototipo armado sin él (dejando uno fuera).
"""

import re
import statistics
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import psycopg
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize as l2_normalize

from observatory.basket import Basket, BasketItem, StoreProduct, matches, normalize

NAME_WEIGHT = 0.85
SUBCATEGORY_WEIGHT = 0.15
NGRAMS = (3, 5)
THRESHOLD_QUANTILE = 0.1
MIN_THRESHOLD = 0.35
DEFAULT_THRESHOLD = 0.5
MIN_MATCHED_FOR_THRESHOLD = 3
MIN_MATCHED_FOR_DOUBTS = 5
DOUBTS = 3
EVALUATION_TOP = 10
# Con pocos productos (pruebas, catálogos chicos) no se descartan n-gramas raros.
MIN_DF_CATALOG = 50

# Cantidades y palabras de presentación: no dicen qué producto es.
NOISE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:kg|kgs|gr|grs|g|ml|lt|lts|l|cc|u|un|und|unid|uni)?\b"
    r"|\b(?:kg|gr|grs|ml|lt|lts|x|hipermaxi|unidad|unidades|bolsa|caja|pack|sachet)\b"
)

# Por qué las reglas no aceptan un producto, en el orden en que se revisa.
REASON_NAME = "nombre"
REASON_EXCLUDED = "excluido"
REASON_SUBCATEGORY = "subcategoria"
REASON_PRESENTATION = "presentacion"
REASON_ACCEPTED = "aceptado"


@dataclass(frozen=True)
class CatalogProduct:
    """Producto de tienda vigente, con el ítem al que está emparejado si lo está."""

    product_id: int
    name: str
    subcategory: str | None
    content: Decimal | None
    unit: str | None
    url: str
    item_code: str | None


@dataclass(frozen=True)
class Suggestion:
    """Producto con su similitud al ítem y por qué las reglas no lo aceptan."""

    product: CatalogProduct
    score: float
    reason: str


@dataclass(frozen=True)
class ItemReport:
    """Resultado del modelo para un ítem de la canasta."""

    code: str
    name: str
    matched: int
    threshold: float
    candidates: tuple[Suggestion, ...]
    doubtful: tuple[Suggestion, ...]


@dataclass(frozen=True)
class Evaluation:
    """Si se quita un producto de las reglas, ¿el modelo lo vuelve a encontrar?"""

    cases: int
    found_in_top: int
    top: int
    median_rank: float | None


@dataclass(frozen=True)
class SuggestionReport:
    """Resultado completo: un informe por ítem y la evaluación del modelo."""

    items: tuple[ItemReport, ...]
    evaluation: Evaluation
    catalog_size: int


def clean_name(text: str | None) -> str:
    """Nombre sin tildes, cantidades ni palabras de presentación."""
    without_noise = NOISE.sub(" ", normalize(text or ""))
    return re.sub(r"\s+", " ", without_noise).strip()


def rejection_reason(item: BasketItem, product: CatalogProduct) -> str:
    """Primera regla que deja fuera al producto, o 'aceptado' si las cumple todas."""
    name = normalize(product.name)
    if not any(pattern.search(name) for pattern in item.include):
        return REASON_NAME
    if any(pattern.search(name) for pattern in item.exclude):
        return REASON_EXCLUDED
    if item.subcategories and product.subcategory not in item.subcategories:
        return REASON_SUBCATEGORY
    store_product = StoreProduct(
        product.product_id, product.name, product.subcategory, product.content, product.unit
    )
    if not matches(item, store_product):
        return REASON_PRESENTATION
    return REASON_ACCEPTED


def vectorize(basket: Basket, products: list[CatalogProduct]) -> tuple[csr_matrix, csr_matrix]:
    """Vectores L2 de los productos y de los nombres de los ítems, en el mismo espacio."""
    names = [clean_name(product.name) for product in products]
    names += [clean_name(item.name) for item in basket.items]
    subcategories = [clean_name(product.subcategory) for product in products]
    subcategories += [
        " ".join(sorted(clean_name(sub) for sub in item.subcategories)) for item in basket.items
    ]
    min_df = 1
    if len(products) >= MIN_DF_CATALOG:
        min_df = 2
    name_matrix = TfidfVectorizer(
        analyzer="char_wb", ngram_range=NGRAMS, sublinear_tf=True, min_df=min_df
    ).fit_transform(names)
    blocks = [name_matrix * NAME_WEIGHT**0.5]
    # Sin subcategorías (catálogos de prueba) se compara solo por nombre.
    if any(subcategories):
        subcategory_matrix = TfidfVectorizer(
            analyzer="word", token_pattern=r"[a-z]+"
        ).fit_transform(subcategories)
        blocks.append(subcategory_matrix * SUBCATEGORY_WEIGHT**0.5)
    matrix = l2_normalize(hstack(blocks).tocsr())
    return matrix[: len(products)], matrix[len(products) :]


def _unit_vector(vector: np.ndarray) -> np.ndarray:
    """Vector de largo 1 (el vector nulo queda igual)."""
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def leave_one_out_scores(vectors: csr_matrix, indices: list[int]) -> np.ndarray:
    """Similitud de cada producto aceptado con el prototipo armado sin él."""
    if len(indices) < 2:
        return np.array([])
    rows = vectors[indices]
    total = np.asarray(rows.sum(axis=0))[0]
    scores = []
    for position in range(len(indices)):
        own = rows[position].toarray()[0]
        prototype = _unit_vector(total - own)
        scores.append(float(own @ prototype))
    return np.array(scores)


def item_threshold(loo_scores: np.ndarray) -> float:
    """Umbral de un ítem: percentil 10 de sus productos aceptados, con un piso."""
    if len(loo_scores) < MIN_MATCHED_FOR_THRESHOLD:
        return DEFAULT_THRESHOLD
    return max(float(np.quantile(loo_scores, THRESHOLD_QUANTILE)), MIN_THRESHOLD)


def suggest(basket: Basket, products: list[CatalogProduct], top: int = 5) -> SuggestionReport:
    """Candidatos y emparejamientos dudosos por ítem, más la evaluación del modelo."""
    if not products:
        raise ValueError("No hay productos de tienda con precio para comparar")
    vectors, item_vectors = vectorize(basket, products)
    units = np.array([product.unit for product in products])
    unmatched = np.array([product.item_code is None for product in products])
    reports = []
    ranks: list[int] = []
    for position, item in enumerate(basket.items):
        indices = [
            index for index, product in enumerate(products) if product.item_code == item.code
        ]
        if indices:
            mean = np.asarray(vectors[indices].mean(axis=0))[0]
            prototype = _unit_vector(mean)
        else:
            prototype = item_vectors[position].toarray()[0]
        scores = vectors @ prototype
        loo = leave_one_out_scores(vectors, indices)
        threshold = item_threshold(loo)
        pool = np.flatnonzero((units == item.unit) & unmatched)
        candidates = []
        for index in pool[np.argsort(-scores[pool])]:
            score = float(scores[index])
            if score < threshold or len(candidates) == top:
                break
            reason = rejection_reason(item, products[index])
            # Lo que una regla excluye a propósito no se vuelve a sugerir.
            if reason == REASON_EXCLUDED:
                continue
            candidates.append(Suggestion(products[index], score, reason))
        doubtful = ()
        if len(indices) >= MIN_MATCHED_FOR_DOUBTS:
            order = np.argsort(loo)[:DOUBTS]
            doubtful = tuple(
                Suggestion(products[indices[k]], float(loo[k]), REASON_ACCEPTED)
                for k in order
                if loo[k] < threshold
            )
        ranks.extend(_retrieval_ranks(vectors, indices, pool))
        reports.append(
            ItemReport(
                code=item.code,
                name=item.name,
                matched=len(indices),
                threshold=threshold,
                candidates=tuple(candidates),
                doubtful=doubtful,
            )
        )
    median_rank = None
    if ranks:
        median_rank = statistics.median(ranks)
    evaluation = Evaluation(
        cases=len(ranks),
        found_in_top=sum(rank <= EVALUATION_TOP for rank in ranks),
        top=EVALUATION_TOP,
        median_rank=median_rank,
    )
    return SuggestionReport(tuple(reports), evaluation, len(products))


def _retrieval_ranks(vectors: csr_matrix, indices: list[int], pool: np.ndarray) -> list[int]:
    """Puesto de cada producto aceptado entre los no emparejados, con el prototipo sin él."""
    if len(indices) < 2:
        return []
    rows = vectors[indices]
    total = np.asarray(rows.sum(axis=0))[0]
    pool_vectors = vectors[pool]
    ranks = []
    for position in range(len(indices)):
        own = rows[position].toarray()[0]
        prototype = _unit_vector(total - own)
        own_score = own @ prototype
        better = int((pool_vectors @ prototype > own_score).sum())
        ranks.append(better + 1)
    return ranks


CATALOG_QUERY = """
SELECT p.id, p.nombre, p.subcategoria, p.contenido_cantidad, p.contenido_unidad, p.url,
       pc.codigo
FROM producto p
LEFT JOIN emparejamiento e ON e.producto_id = p.id
LEFT JOIN producto_canonico pc ON pc.id = e.producto_canonico_id
WHERE p.id IN (
    SELECT producto_id FROM observacion_precio
    WHERE fecha = (SELECT max(fecha) FROM observacion_precio)
)
ORDER BY p.id
"""


def load_catalog(connection: psycopg.Connection) -> list[CatalogProduct]:
    """Productos con precio el último día, con su emparejamiento actual."""
    return [CatalogProduct(*row) for row in connection.execute(CATALOG_QUERY)]
