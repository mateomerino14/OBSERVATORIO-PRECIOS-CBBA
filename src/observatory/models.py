"""Estructuras que se intercambian entre las fuentes y el almacenamiento."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Branch:
    """Sucursal de una cadena tal como la publica su sitio."""

    code: str
    name: str
    city: str
    external_id: str | None = None
    address: str | None = None


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
    category: str | None = None
    subcategory: str | None = None
    sold_by_weight: bool = False


@dataclass(frozen=True)
class FetchedPage:
    """Resultado de pedir una página de catálogo: sus observaciones o el error que dio."""

    label: str
    observations: list[PriceObservation] = field(default_factory=list)
    error: str | None = None
