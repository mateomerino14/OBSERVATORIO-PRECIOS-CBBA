"""Línea de comandos: migrar | recolectar | importar | canasta | exportar."""

import argparse
import logging
import sys
from pathlib import Path

from observatory.basket import BasketDefinitionError, load_basket, sync_basket
from observatory.collector import collect, collect_exchange_rates, today_in_bolivia
from observatory.config import MissingSettingError, load_settings
from observatory.db import connect, migrate
from observatory.export import build_dashboard, write_dashboard
from observatory.http_client import PoliteClient
from observatory.sources import bcb, defensoria, hipermaxi, paralelo
from observatory.storage import save_exchange_rates, save_market_prices

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 2
DEFAULT_CITY = "cochabamba"


def build_parser() -> argparse.ArgumentParser:
    """Define los comandos y opciones disponibles."""
    parser = argparse.ArgumentParser(prog="observatorio", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrar", help="Crea o actualiza las tablas de la base")

    collect_parser = commands.add_parser("recolectar", help="Recolecta los datos del día")
    collect_parser.add_argument("fuente", choices=["hipermaxi", "bcb"])
    collect_parser.add_argument("--ciudad", default=DEFAULT_CITY, help="Solo para hipermaxi")
    collect_parser.add_argument(
        "--max-paginas", type=int, help="Hipermaxi: máximo de páginas de 50 productos"
    )
    collect_parser.add_argument(
        "--anios",
        type=int,
        nargs="+",
        help="BCB: años a cargar (por defecto, el año en curso)",
    )

    import_parser = commands.add_parser(
        "importar", help="Carga datos versionados en fuentes/ (Defensoría, dólar paralelo)"
    )
    import_parser.add_argument("fuente", choices=["defensoria", "paralelo"])
    import_parser.add_argument("archivo", type=Path, help="CSV de la carpeta fuentes/")
    import_parser.add_argument("--ciudad", default=DEFAULT_CITY)

    export_parser = commands.add_parser("exportar", help="Genera el JSON del dashboard")
    export_parser.add_argument("--canasta", type=Path, required=True, help="TOML de la canasta")
    export_parser.add_argument("--salida", type=Path, required=True, help="Archivo JSON a escribir")
    export_parser.add_argument("--ciudad", default=DEFAULT_CITY)

    basket_parser = commands.add_parser("canasta", help="Carga o revisa una canasta")
    basket_parser.add_argument("accion", choices=["cargar", "revisar"])
    basket_parser.add_argument("archivo", type=Path, help="Archivo TOML de la canasta")
    return parser


REVIEW_QUERY = """
SELECT pc.codigo, s.nombre, p.nombre, o.precio, p.contenido_cantidad, p.contenido_unidad
FROM canasta c
JOIN canasta_item ci ON ci.canasta_id = c.id
JOIN producto_canonico pc ON pc.id = ci.producto_canonico_id
JOIN emparejamiento e ON e.producto_canonico_id = pc.id
JOIN producto p ON p.id = e.producto_id
JOIN observacion_precio o ON o.producto_id = p.id
JOIN sucursal s ON s.id = o.sucursal_id
WHERE c.codigo = %s
  AND o.fecha = (SELECT max(fecha) FROM observacion_precio)
  AND s.id = (SELECT min(id) FROM sucursal)
ORDER BY pc.codigo, o.precio / p.contenido_cantidad
"""


def run_basket(arguments: argparse.Namespace) -> int:
    """Carga la canasta y rehace sus emparejamientos; con 'revisar' además lista los productos."""
    settings = load_settings()
    basket = load_basket(arguments.archivo)
    with connect(settings.database_url) as connection:
        counts = sync_basket(connection, basket)
        print(f"Canasta {basket.code}: {len(basket.items)} productos")
        for item in basket.items:
            print(f"  {item.code:<14} {counts[item.code]:>4} productos de tienda")
        if arguments.accion == "revisar":
            print_review(connection, basket.code)
    missing = [code for code, count in counts.items() if count == 0]
    if missing:
        print(f"Sin productos de tienda: {', '.join(missing)}", file=sys.stderr)
    # Que falten algunos ítems es esperable (frescos); que falten todos indica un error.
    if len(missing) == len(counts):
        return EXIT_FAILED
    return EXIT_OK


def print_review(connection, basket_code: str) -> None:
    """Muestra, para la primera sucursal y el último día, qué producto quedó en cada ítem."""
    current = None
    for code, branch, name, price, quantity, unit in connection.execute(
        REVIEW_QUERY, (basket_code,)
    ):
        if code != current:
            print(f"\n[{code}] {branch}")
            current = code
        unit_price = price / quantity
        print(f"  Bs {price:>7}  {unit_price:.4f} Bs/{unit}  {name}")


def run_import(arguments: argparse.Namespace) -> int:
    """Carga un CSV de fuentes/: precios de mercado o cierres del dólar paralelo."""
    settings = load_settings()
    if arguments.fuente == "paralelo":
        rates = paralelo.read_csv(arguments.archivo)
        with connect(settings.database_url) as connection:
            saved = save_exchange_rates(connection, paralelo.SOURCE_CODE, rates)
        print(f"{saved} cierres del dólar paralelo de {rates[0].day:%Y-%m} a {rates[-1].day:%Y-%m}")
        return EXIT_OK
    rows = defensoria.read_csv(arguments.archivo, arguments.ciudad)
    with connect(settings.database_url) as connection:
        saved = save_market_prices(connection, rows)
    months = sorted({row["mes"] for row in rows})
    print(f"{saved} precios de mercado de {months[0]:%Y-%m} a {months[-1]:%Y-%m}")
    return EXIT_OK


def run_export(arguments: argparse.Namespace) -> int:
    """Escribe el JSON que lee el sitio del dashboard."""
    settings = load_settings()
    basket = load_basket(arguments.canasta)
    with connect(settings.database_url) as connection:
        document = build_dashboard(connection, basket, arguments.ciudad)
    path = write_dashboard(document, arguments.salida)
    print(f"Dashboard exportado en {path} (último día: {document['ultimo_dia']})")
    return EXIT_OK


def run_migrate() -> int:
    """Aplica las migraciones pendientes."""
    settings = load_settings()
    with connect(settings.database_url) as connection:
        applied = migrate(connection)
    if applied:
        print(f"Migraciones aplicadas: {', '.join(applied)}")
    else:
        print("La base ya está al día")
    return EXIT_OK


class InvalidYearsError(ValueError):
    """Se pidieron años que el BCB no publica."""


def exchange_rate_years(requested: list[int] | None) -> list[int]:
    """Años a cargar del BCB: los pedidos, o el año en curso."""
    current_year = today_in_bolivia().year
    if not requested:
        return [current_year]
    invalid = [year for year in requested if not bcb.FIRST_YEAR <= year <= current_year]
    if invalid:
        raise InvalidYearsError(f"Años fuera de rango ({bcb.FIRST_YEAR}-{current_year}): {invalid}")
    return sorted(set(requested))


def run_collect(arguments: argparse.Namespace) -> int:
    """Recolecta una fuente y devuelve código de error si la corrida falló."""
    settings = load_settings()
    client = PoliteClient(delay_seconds=settings.delay_seconds)
    try:
        with connect(settings.database_url) as connection:
            if arguments.fuente == "bcb":
                summary = collect_exchange_rates(
                    client, connection, exchange_rate_years(arguments.anios)
                )
            else:
                summary = collect(
                    connection,
                    source=hipermaxi.CHAIN_CODE,
                    pages=hipermaxi.iter_pages(client, arguments.ciudad),
                    observed_on=today_in_bolivia(),
                    max_pages=arguments.max_paginas,
                )
    finally:
        client.close()
    print(
        f"{summary.status}: {summary.observations} registros en {summary.pages_ok} páginas, "
        f"{summary.pages_failed} con error"
    )
    if summary.status in ("fallida", "bloqueada"):
        return EXIT_FAILED
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del comando observatorio."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "migrar":
            return run_migrate()
        if arguments.command == "canasta":
            return run_basket(arguments)
        if arguments.command == "importar":
            return run_import(arguments)
        if arguments.command == "exportar":
            return run_export(arguments)
        return run_collect(arguments)
    except (
        MissingSettingError,
        InvalidYearsError,
        BasketDefinitionError,
        defensoria.DefensoriaParseError,
        paralelo.ParallelRateError,
    ) as error:
        print(error, file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
