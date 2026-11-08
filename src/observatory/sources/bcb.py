"""Fuente BCB: tipo de cambio oficial diario desde el PDF histórico anual del Banco Central."""

import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pdfplumber

SOURCE_CODE = "bcb_oficial"
PDF_URL = "https://www.bcb.gob.bo/tiposDeCambioHistorico/pdf.php?anio={year}"
FIRST_YEAR = 2008

MONTHS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
# Desde junio de 2026 el BCB publica un solo valor "oficial"; antes, venta y compra.
COLUMN_KINDS = {"VENTA", "COMPRA", "OFICIAL"}
RATE_PATTERN = re.compile(r"^\d{1,2},\d{2,4}$")
MAX_DAY = 31
# Distancia horizontal máxima, en puntos, entre un número y la columna a la que pertenece.
COLUMN_TOLERANCE = 20.0
ROW_TOLERANCE = 3.0


class BcbParseError(ValueError):
    """El PDF no tiene la tabla de cotizaciones esperada."""


@dataclass(frozen=True)
class ExchangeRate:
    """Cotización oficial de un día: venta y, si la hay, compra."""

    day: date
    sell: Decimal
    buy: Decimal | None


@dataclass(frozen=True)
class _Column:
    """Columna de la tabla: mes, tipo de valor y posición horizontal."""

    month: int
    kind: str
    center: float


def pdf_url(year: int) -> str:
    """URL del PDF anual de cotizaciones."""
    return PDF_URL.format(year=year)


def parse_rates_pdf(content: bytes, year: int) -> list[ExchangeRate]:
    """Lee la tabla anual del PDF ubicando cada número bajo la columna que le corresponde."""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        words = [word for page in pdf.pages for word in page.extract_words()]
    rows = _group_rows(words)
    columns = _find_columns(rows)
    values: dict[tuple[date, str], Decimal] = {}
    for row in rows:
        day_number = _day_number(row)
        if day_number is None:
            continue
        for word in row[1:]:
            if not RATE_PATTERN.match(word["text"]):
                continue
            column = _nearest_column(columns, _center(word))
            if column is None:
                continue
            try:
                day = date(year, column.month, day_number)
            except ValueError:
                continue
            values[(day, column.kind)] = Decimal(word["text"].replace(",", "."))
    return _combine(values)


def _group_rows(words: list[dict]) -> list[list[dict]]:
    """Agrupa las palabras en filas por su altura y las ordena de izquierda a derecha."""
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if rows and abs(rows[-1][0]["top"] - word["top"]) <= ROW_TOLERANCE:
            rows[-1].append(word)
            continue
        rows.append([word])
    for row in rows:
        row.sort(key=lambda item: item["x0"])
    return rows


def _find_columns(rows: list[list[dict]]) -> list[_Column]:
    """Arma las columnas a partir de la fila de meses y la fila de VENTA/COMPRA/OFICIAL."""
    month_row = next((row for row in rows if _count(row, MONTHS) >= len(MONTHS) // 2), None)
    kind_row = next((row for row in rows if _count(row, COLUMN_KINDS) >= len(MONTHS)), None)
    if month_row is None or kind_row is None:
        raise BcbParseError("No se encontró el encabezado de meses de la tabla")
    months = [(MONTHS[word["text"]], _center(word)) for word in month_row if word["text"] in MONTHS]
    columns = []
    for word in kind_row:
        if word["text"] not in COLUMN_KINDS:
            continue
        center = _center(word)
        month = min(months, key=lambda item: abs(item[1] - center))[0]
        columns.append(_Column(month=month, kind=word["text"], center=center))
    return columns


def _nearest_column(columns: list[_Column], center: float) -> _Column | None:
    """Columna más cercana a un número, si está dentro de la tolerancia."""
    column = min(columns, key=lambda item: abs(item.center - center))
    if abs(column.center - center) > COLUMN_TOLERANCE:
        return None
    return column


def _combine(values: dict[tuple[date, str], Decimal]) -> list[ExchangeRate]:
    """Une venta, compra y oficial de cada día; el valor oficial cuenta como venta."""
    days = sorted({day for day, _ in values})
    rates = []
    for day in days:
        sell = values.get((day, "OFICIAL"))
        if sell is None:
            sell = values.get((day, "VENTA"))
        if sell is None:
            continue
        rates.append(ExchangeRate(day=day, sell=sell, buy=values.get((day, "COMPRA"))))
    return rates


def _day_number(row: list[dict]) -> int | None:
    """Número de día de una fila de datos (1 a 31); None si es otra fila."""
    first = row[0]["text"]
    if not first.isdigit():
        return None
    number = int(first)
    if 1 <= number <= MAX_DAY:
        return number
    return None


def _count(row: list[dict], vocabulary: set[str] | dict[str, int]) -> int:
    """Cuántas palabras de la fila pertenecen al vocabulario."""
    return sum(1 for word in row if word["text"] in vocabulary)


def _center(word: dict) -> float:
    """Centro horizontal de una palabra."""
    return (word["x0"] + word["x1"]) / 2
