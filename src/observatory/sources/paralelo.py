"""Fuente dólar paralelo: cierres mensuales armados a partir de los boletines del CEED."""

import calendar
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from observatory.sources.bcb import ExchangeRate

SOURCE_CODE = "paralelo"
CSV_COLUMNS = {"mes", "fecha_dato", "venta", "metodo", "fuente_url", "nota"}
METHODS = {"a_12_meses", "acumulada_anual", "variacion_mensual"}


class ParallelRateError(ValueError):
    """El CSV del dólar paralelo tiene un error de formato."""


def month_end(month: str) -> date:
    """Último día de un mes AAAA-MM: fecha con la que se guarda el cierre."""
    year, number = (int(part) for part in month.split("-"))
    return date(year, number, calendar.monthrange(year, number)[1])


def read_csv(path: Path) -> list[ExchangeRate]:
    """Lee los cierres mensuales del paralelo; cada uno se fecha el último día de su mes.

    La columna fecha_dato guarda cuándo se midió realmente el valor (en 2024 son valores
    puntuales cercanos al cierre) y queda solo como procedencia.
    """
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing = CSV_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ParallelRateError(f"{path.name}: faltan columnas {sorted(missing)}")
        rates = []
        for line in reader:
            if line["metodo"] not in METHODS:
                raise ParallelRateError(f"{path.name}: método desconocido {line['metodo']}")
            sell = Decimal(line["venta"])
            if sell <= 0:
                raise ParallelRateError(f"{path.name}: valor inválido en {line['mes']}")
            rates.append(ExchangeRate(day=month_end(line["mes"]), sell=sell, buy=None))
    return rates
