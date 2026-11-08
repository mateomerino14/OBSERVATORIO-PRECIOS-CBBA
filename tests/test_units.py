from decimal import Decimal

import pytest

from observatory.units import Content, parse_content


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Arroz Caisy Especial 5 kg", Content(Decimal(5000), "g")),
        ("Arroz Goya Jasmine 340 gr", Content(Decimal(340), "g")),
        ("Azucar Guabira de 5 Kl", Content(Decimal(5000), "g")),
        ("Harina Famosa 1 K", Content(Decimal(1000), "g")),
        ("Leche Fresca Natural Pil UHT 900 Ml", Content(Decimal(900), "ml")),
        ("Gaseosa Seven Up 3 Lts", Content(Decimal(3000), "ml")),
        ("Aceite Fino Light 1,8 L", Content(Decimal(1800), "ml")),
        ("Aceite Fino 1.8 Lt", Content(Decimal(1800), "ml")),
        ("Huevo Marron Grande Sofia 30 U", Content(Decimal(30), "u")),
        ("Servilleta de Papel Perlita 500 Unid", Content(Decimal(500), "u")),
        ("Papel Toalla de Cocina Clasica Nova 2 Rollos", Content(Decimal(2), "u")),
        ("Insecticida en Aerosol Baygon 300 Ml.", Content(Decimal(300), "ml")),
        ("Hamburguesa de Carne Sin Condimento en Bandeja x kg", Content(Decimal(1000), "g")),
    ],
)
def test_parse_content_normalizes_store_formats(name: str, expected: Content) -> None:
    assert parse_content(name) == expected


@pytest.mark.parametrize(
    "name",
    ["Pan Frances Por Unidad", "Silpancho de Res en Caja Sofia", "Gaseosa 7Up"],
)
def test_parse_content_returns_none_without_measure(name: str) -> None:
    assert parse_content(name) is None


def test_parse_content_does_not_take_brand_digits_as_measure() -> None:
    assert parse_content("Galleta 3D Kris 120 G") == Content(Decimal(120), "g")
