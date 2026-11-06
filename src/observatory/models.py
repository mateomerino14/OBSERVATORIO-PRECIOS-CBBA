"""Estructuras que se intercambian entre las fuentes y el almacenamiento."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Branch:
    """Sucursal de una cadena tal como aparece en su sitio."""

    code: str
    name: str
    city: str


@dataclass(frozen=True)
class PriceObservation:
    """Precio de un producto en una sucursal en el momento de la captura."""

    chain_code: str
    branch: Branch
    external_code: str
    name: str
    brand: str | None
    url: str
    price: Decimal
    regular_price: Decimal | None
    available: bool
    stock: int | None
