"""Línea de comandos: observatorio migrar | observatorio recolectar <fuente>."""

import argparse
import logging
import sys

from observatory.collector import collect, today_in_bolivia
from observatory.config import MissingSettingError, load_settings
from observatory.db import connect, migrate
from observatory.http_client import PoliteClient
from observatory.sources import hipermaxi

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 2
DEFAULT_CITY = "cochabamba"


def build_parser() -> argparse.ArgumentParser:
    """Define los comandos y opciones disponibles."""
    parser = argparse.ArgumentParser(prog="observatorio", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrar", help="Crea o actualiza las tablas de la base")

    collect_parser = commands.add_parser("recolectar", help="Recolecta los precios del día")
    collect_parser.add_argument("fuente", choices=["hipermaxi"])
    collect_parser.add_argument("--ciudad", default=DEFAULT_CITY)
    collect_parser.add_argument("--limite", type=int, help="Máximo de productos (para pruebas)")
    collect_parser.add_argument("--sitemap", help="URL de sitemap alternativa")
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


def run_collect(arguments: argparse.Namespace) -> int:
    """Recolecta una fuente y devuelve código de error si la corrida falló."""
    settings = load_settings()
    client = PoliteClient(delay_seconds=settings.delay_seconds)
    sitemap = arguments.sitemap or hipermaxi.SITEMAP_URL
    try:
        with connect(settings.database_url) as connection:
            urls = hipermaxi.discover_product_urls(client, arguments.ciudad, sitemap)
            summary = collect(
                client,
                connection,
                source=hipermaxi.CHAIN_CODE,
                urls=urls,
                parse_page=hipermaxi.parse_product_page,
                observed_on=today_in_bolivia(),
                limit=arguments.limite,
            )
    finally:
        client.close()
    print(f"{summary.status}: {summary.pages_ok} productos, {summary.pages_failed} con error")
    if summary.status == "fallida":
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
    except MissingSettingError as error:
        print(error, file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
