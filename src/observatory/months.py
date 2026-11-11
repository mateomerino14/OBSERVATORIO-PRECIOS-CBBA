"""Aritmética de meses: cada mes se representa con la fecha de su primer día."""

from datetime import date

MONTHS_IN_YEAR = 12
DECEMBER = 12


def shift_months(month: date, delta: int) -> date:
    """Primer día del mes que queda `delta` meses después (o antes, si es negativo)."""
    index = month.year * MONTHS_IN_YEAR + month.month - 1 + delta
    return date(index // MONTHS_IN_YEAR, index % MONTHS_IN_YEAR + 1, 1)


def next_month(month: date) -> date:
    """Primer día del mes siguiente."""
    return shift_months(month, 1)


def previous_month(month: date) -> date:
    """Primer día del mes anterior."""
    return shift_months(month, -1)
