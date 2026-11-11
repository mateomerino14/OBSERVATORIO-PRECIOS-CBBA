"""Extrae los precios de mercado de Cochabamba de los sondeos mensuales de la Defensoría.

Uso:
    python scripts/extraer_defensoria.py <carpeta_con_pdf> fuentes/defensoria/cochabamba.csv

Necesita `pdftotext` (poppler-utils). Cada mes aparece en dos informes: como mes del informe
y como mes anterior en el siguiente. Se toma el valor del informe del propio mes; si falta,
el del informe siguiente. Si los dos existen y no coinciden, se informa.
"""

import csv
import logging
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from observatory.sources.defensoria import (
    MONTHS,
    MarketPrice,
    normalize,
    parse_city_table,
    presentation,
)

BASE_URL = "https://www.defensoria.gob.bo/uploads/files/"
# Informes publicados sin año en el nombre del archivo.
DEFAULT_YEAR = 2025
COLUMNS = [
    "mes",
    "producto",
    "precio",
    "presentacion_cantidad",
    "presentacion_unidad",
    "descripcion",
    "informe",
    "variacion_verificada",
    "fuente_url",
]

logger = logging.getLogger("extraer_defensoria")


def report_date(pdf: Path) -> date:
    """Mes del informe, leído del nombre del archivo."""
    name = normalize(pdf.stem)
    match = re.search(r"(" + "|".join(MONTHS) + r")-?(\d{4})?$", name)
    if match is None:
        raise ValueError(f"No se reconoce el mes en {pdf.name}")
    year = DEFAULT_YEAR
    if match.group(2):
        year = int(match.group(2))
    return date(year, MONTHS[match.group(1)], 1)


def pdf_text(pdf: Path) -> str:
    """Texto del PDF conservando la disposición en columnas."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=False
    )
    return result.stdout


def consolidate(prices: list[MarketPrice]) -> dict[tuple[str, date], MarketPrice]:
    """Un precio por producto y mes, prefiriendo el informe del propio mes."""
    chosen: dict[tuple[str, date], MarketPrice] = {}
    for price in sorted(prices, key=lambda item: item.report):
        key = (price.product, price.month)
        current = chosen.get(key)
        if current is None:
            chosen[key] = price
            continue
        if current.price != price.price:
            logger.warning(
                "%s %s: %s en el informe %s y %s en el %s",
                price.product,
                price.month,
                current.price,
                current.report,
                price.price,
                price.report,
            )
        if price.report == price.month:
            chosen[key] = price
    return chosen


def main(source_dir: Path, output: Path) -> int:
    """Lee todos los PDF de la carpeta y escribe el CSV consolidado."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    prices: list[MarketPrice] = []
    urls: dict[date, str] = {}
    for pdf in sorted(source_dir.glob("*.pdf")):
        report = report_date(pdf)
        try:
            found = parse_city_table(pdf_text(pdf), report)
        except ValueError as error:
            logger.warning("%s: %s", pdf.name, error)
            continue
        urls[report] = BASE_URL + pdf.name
        prices.extend(found)
        logger.info("%s: %s precios", report, len(found))
    rows = consolidate(prices)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for (product, month), price in sorted(
            rows.items(), key=lambda item: (item[0][1], item[0][0])
        ):
            quantity, unit = presentation(product)
            writer.writerow(
                [
                    month.isoformat()[:7],
                    product,
                    price.price,
                    quantity,
                    unit,
                    price.description,
                    price.report.isoformat()[:7],
                    str(price.verified).lower(),
                    urls[price.report],
                ]
            )
    logger.info("%s filas en %s", len(rows), output)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
