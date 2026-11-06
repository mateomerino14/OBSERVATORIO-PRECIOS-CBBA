"""Línea de comandos: observatorio migrar | observatorio recolectar <fuente>."""

import argparse
import logging
import sys

from observatory.collector import collect, collect_exchange_rates, today_in_bolivia
from observatory.config import MissingSettingError, load_settings
from observatory.db import connect, migrate
from observatory.http_client import PoliteClient
from observatory.sources import bcb, hipermaxi

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
    return parser


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
        return run_collect(arguments)
    except (MissingSettingError, InvalidYearsError) as error:
        print(error, file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
