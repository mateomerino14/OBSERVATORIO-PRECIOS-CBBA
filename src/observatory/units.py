"""Lectura y normalización de la presentación de un producto a partir de su nombre."""

import re
from dataclasses import dataclass
from decimal import Decimal

# Cada unidad que usan las tiendas se lleva a gramos, mililitros o unidades.
UNIT_FACTORS: dict[str, tuple[str, Decimal]] = {
    "kg": ("g", Decimal(1000)),
    "kl": ("g", Decimal(1000)),
    "kilo": ("g", Decimal(1000)),
    "kilos": ("g", Decimal(1000)),
    "k": ("g", Decimal(1000)),
    "g": ("g", Decimal(1)),
    "gr": ("g", Decimal(1)),
    "grs": ("g", Decimal(1)),
    "gramos": ("g", Decimal(1)),
    "l": ("ml", Decimal(1000)),
    "lt": ("ml", Decimal(1000)),
    "lts": ("ml", Decimal(1000)),
    "litro": ("ml", Decimal(1000)),
    "litros": ("ml", Decimal(1000)),
    "ml": ("ml", Decimal(1)),
    "cc": ("ml", Decimal(1)),
    "cm3": ("ml", Decimal(1)),
    "u": ("u", Decimal(1)),
    "un": ("u", Decimal(1)),
    "und": ("u", Decimal(1)),
    "uni": ("u", Decimal(1)),
    "unid": ("u", Decimal(1)),
    "unidades": ("u", Decimal(1)),
    "rollos": ("u", Decimal(1)),
}

# Las unidades largas van primero para que "kg" no se lea como "k".
_UNITS_PATTERN = "|".join(sorted(UNIT_FACTORS, key=len, reverse=True))
CONTENT_PATTERN = re.compile(
    rf"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*({_UNITS_PATTERN})\.?(?![\w])",
    re.IGNORECASE,
)
GRAMS_PER_KILO = Decimal(1000)
PER_KILO_PATTERN = re.compile(r"\bx\s*kg\b", re.IGNORECASE)


@dataclass(frozen=True)
class Content:
    """Presentación normalizada: cantidad en g, ml o unidades."""

    quantity: Decimal
    unit: str


def parse_content(name: str) -> Content | None:
    """Extrae la presentación del nombre del producto; devuelve None si no la encuentra."""
    if PER_KILO_PATTERN.search(name):
        return Content(GRAMS_PER_KILO, "g")
    matches = CONTENT_PATTERN.findall(name)
    if not matches:
        return None
    # Si el nombre trae varias medidas, la última suele ser la presentación de venta.
    amount_text, unit_text = matches[-1]
    base_unit, factor = UNIT_FACTORS[unit_text.lower()]
    amount = Decimal(amount_text.replace(",", "."))
    return Content((amount * factor).normalize(), base_unit)
