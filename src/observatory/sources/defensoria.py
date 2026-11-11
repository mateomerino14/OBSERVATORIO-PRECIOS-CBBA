"""Fuente Defensoría del Pueblo: precios de mercado de su sondeo mensual, desde el texto del PDF."""

import csv
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

SOURCE_CODE = "defensoria"
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
MONTH_PATTERN = re.compile(r"\b(" + "|".join(MONTHS) + r")\b")
NUMBER = r"-?\d{1,4}(?:[.,]\d{1,2})?"
DATA_LINE = re.compile(rf"^\s*(?P<text>.*?)\s+(?P<numbers>(?:{NUMBER}\s+){{1,7}}{NUMBER})\s*$")
TABLE_END = re.compile(r"^\s*(en (el caso de )?(la ciudad|el municipio)|tabla\s+\d)", re.IGNORECASE)
HEADER_WORDS = re.compile(
    r"(precios|descripci|unidad|medida|variaci|tasa|cantidad|fuente|elaboraci)", re.IGNORECASE
)
# La variación que publica la Defensoría se compara con la calculada; si difieren más que
# esto, la fila probablemente se leyó mal.
VARIATION_TOLERANCE = Decimal("1.5")
CENT = Decimal("0.01")

# Producto de la Defensoría -> expresión que lo reconoce en la descripción (sin tildes).
PRODUCT_PATTERNS: dict[str, re.Pattern] = {
    "platano_cocinar": re.compile(r"platano/postre|cocinar"),
    "platano": re.compile(r"platano o banano|banano"),
    "leche_polvo": re.compile(r"polvo|instantanea"),
    "leche_fluida": re.compile(r"leche (fluida|pasteurizada)"),
    "res_molida": re.compile(r"molida"),
    "pulpa_res": re.compile(r"pulpa"),
    "pollo_entero": re.compile(r"pollo"),
    "margarina": re.compile(r"margarina|mantequilla"),
    "arroz": re.compile(r"arroz"),
    "azucar": re.compile(r"azucar"),
    "harina_trigo": re.compile(r"harina"),
    "fideo": re.compile(r"fideo"),
    "avena": re.compile(r"avena"),
    "aceite": re.compile(r"aceite"),
    "huevos": re.compile(r"huevo"),
    "papaya": re.compile(r"papaya"),
    "manzana": re.compile(r"manzana"),
    "naranja": re.compile(r"naranja"),
    "cebolla": re.compile(r"cebolla"),
    "tomate": re.compile(r"tomate"),
    "zanahoria": re.compile(r"zanahoria"),
}

# Presentación en la que la Defensoría cotiza cada producto, en unidad base.
# 1 libra = 460 g. La cuartilla se toma como 6 libras (2.760 g): es el valor con el que los
# precios extraídos reproducen el costo de canasta publicado (Bs 171 en enero y Bs 247 en
# diciembre de 2025 para Cochabamba), porque la canasta pide cebolla y zanahoria en libras.
POUND_GRAMS = Decimal(460)
CUARTILLA_GRAMS = POUND_GRAMS * 6
PRESENTATIONS: dict[str, tuple[Decimal, str]] = {
    "arroz": (POUND_GRAMS, "g"),
    "azucar": (POUND_GRAMS, "g"),
    "harina_trigo": (POUND_GRAMS, "g"),
    "fideo": (POUND_GRAMS, "g"),
    "tomate": (POUND_GRAMS, "g"),
    "avena": (Decimal(350), "g"),
    "pulpa_res": (Decimal(1000), "g"),
    "res_molida": (Decimal(1000), "g"),
    "pollo_entero": (Decimal(1000), "g"),
    "leche_fluida": (Decimal(946), "ml"),
    "leche_polvo": (Decimal(760), "g"),
    "margarina": (Decimal(410), "g"),
    "aceite": (Decimal(1000), "ml"),
    "huevos": (Decimal(1), "u"),
    "papaya": (Decimal(1), "u"),
    "manzana": (Decimal(1), "u"),
    "platano_cocinar": (Decimal(1), "u"),
    "naranja": (Decimal(25), "u"),
    "platano": (Decimal(25), "u"),
    "cebolla": (CUARTILLA_GRAMS, "g"),
    "zanahoria": (CUARTILLA_GRAMS, "g"),
}

logger = logging.getLogger(__name__)


class DefensoriaParseError(ValueError):
    """El texto no tiene la tabla de la ciudad pedida."""


@dataclass(frozen=True)
class MarketPrice:
    """Precio de mercado de un producto en un mes, según un informe de la Defensoría."""

    month: date
    product: str
    description: str
    price: Decimal
    report: date
    verified: bool


def normalize(text: str) -> str:
    """Minúsculas y sin tildes."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def identify_product(text: str) -> str | None:
    """Producto cuyo nombre aparece más a la derecha del texto (los nombres partidos en dos
    líneas dejan restos del producto anterior al inicio)."""
    normalized = normalize(text)
    best = None
    best_position = -1
    for code, pattern in PRODUCT_PATTERNS.items():
        for match in pattern.finditer(normalized):
            if match.start() > best_position:
                best = code
                best_position = match.start()
    return best


def parse_city_table(text: str, report: date, city: str = "cochabamba") -> list[MarketPrice]:
    """Lee la tabla de precios de una ciudad del texto de un informe mensual."""
    lines = text.splitlines()
    start = _find_table_start(lines, city)
    end = next(
        (index for index in range(start + 1, len(lines)) if TABLE_END.match(lines[index])),
        len(lines),
    )
    block = lines[start + 1 : end]
    header_months = _header_months(block)
    prices: list[MarketPrice] = []
    seen: set[str] = set()
    pending = ""
    for line in block:
        match = DATA_LINE.match(line)
        if match is None:
            if re.search(r"[a-zA-Z]", line) and not HEADER_WORDS.search(line):
                pending = f"{pending} {line.strip()}".strip()
            continue
        own_text = match["text"].strip()
        product = identify_product(own_text) or identify_product(f"{pending} {own_text}")
        description = re.sub(r"\s{2,}", " ", f"{pending} {own_text}").strip()
        pending = ""
        if product is None or product in seen:
            if product is not None:
                logger.warning("%s: %s repetido; se ignora la segunda fila", report, product)
            continue
        seen.add(product)
        prices.extend(_row_prices(product, description, match["numbers"], header_months, report))
    if not prices:
        raise DefensoriaParseError(f"Sin filas de precios para {city} en el informe {report}")
    return prices


def presentation(product: str) -> tuple[Decimal, str]:
    """Cantidad y unidad base en que la Defensoría cotiza un producto."""
    return PRESENTATIONS[product]


def _find_table_start(lines: list[str], city: str) -> int:
    """Última línea que titula la tabla de precios de la ciudad (antes puede haber índices)."""
    title = re.compile(rf"(tabla|comparaci).*precios.*\b{city}\b", re.IGNORECASE)
    candidates = [index for index, line in enumerate(lines) if title.search(normalize(line))]
    if not candidates:
        raise DefensoriaParseError(f"No se encontró la tabla de {city}")
    return candidates[-1]


def _header_months(block: list[str]) -> list[int]:
    """Meses de las columnas, en orden, leídos de las líneas antes de la primera fila."""
    months: list[int] = []
    for line in block:
        if DATA_LINE.match(line) and identify_product(line):
            break
        months.extend(MONTHS[name] for name in MONTH_PATTERN.findall(normalize(line)))
    return months


def _row_prices(
    product: str, description: str, numbers_text: str, header_months: list[int], report: date
) -> list[MarketPrice]:
    """Convierte los números de una fila en precios por mes; el último número es la variación."""
    numbers = [Decimal(value.replace(",", ".")) for value in numbers_text.split()]
    values = numbers[:-1]
    variation = numbers[-1]
    months = header_months
    if len(months) != len(values):
        # Sin encabezado claro: los dos últimos valores son el mes anterior y el del informe.
        if len(values) < 2:
            return []
        months = [_previous_month(report).month, report.month]
        values = values[-2:]
    # Algunos informes publican la variación contra el mes anterior y otros contra el
    # primer mes de la tabla; vale cualquiera de las dos.
    verified = _variation_matches(values[-2], values[-1], variation) or _variation_matches(
        values[0], values[-1], variation
    )
    if not verified:
        logger.warning("%s %s: la variación publicada no coincide", report, product)
    result = []
    for month_number, value in zip(months, values, strict=True):
        if value <= 0:
            continue
        year = report.year
        if month_number > report.month:
            year -= 1
        result.append(
            MarketPrice(
                month=date(year, month_number, 1),
                product=product,
                description=description,
                price=value.quantize(CENT),
                report=report,
                verified=verified,
            )
        )
    return result


def _variation_matches(previous: Decimal, current: Decimal, published: Decimal) -> bool:
    """Compara la variación porcentual publicada con la calculada a partir de los precios."""
    if previous <= 0:
        return False
    computed = (current / previous - 1) * 100
    return abs(computed - published) <= VARIATION_TOLERANCE


def _previous_month(day: date) -> date:
    """Primer día del mes anterior."""
    if day.month == 1:
        return date(day.year - 1, 12, 1)
    return date(day.year, day.month - 1, 1)


CSV_COLUMNS = {
    "mes",
    "producto",
    "precio",
    "presentacion_cantidad",
    "presentacion_unidad",
    "descripcion",
    "informe",
    "variacion_verificada",
    "fuente_url",
}


def read_csv(path: Path, city: str) -> list[dict[str, object]]:
    """Lee el CSV generado por scripts/extraer_defensoria.py como filas para precio_mercado."""
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing = CSV_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise DefensoriaParseError(f"{path.name}: faltan columnas {sorted(missing)}")
        rows = []
        for line in reader:
            if line["producto"] not in PRESENTATIONS:
                raise DefensoriaParseError(f"{path.name}: producto desconocido {line['producto']}")
            rows.append(
                {
                    "fuente": SOURCE_CODE,
                    "ciudad": city,
                    "producto": line["producto"],
                    "mes": date.fromisoformat(f"{line['mes']}-01"),
                    "precio": Decimal(line["precio"]),
                    "presentacion_cantidad": Decimal(line["presentacion_cantidad"]),
                    "presentacion_unidad": line["presentacion_unidad"],
                    "descripcion": line["descripcion"],
                    "informe": date.fromisoformat(f"{line['informe']}-01"),
                    "verificado": line["variacion_verificada"] == "true",
                    "fuente_url": line["fuente_url"],
                }
            )
    return rows
