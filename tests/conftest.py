"""Fixtures compartidas: base de PostgreSQL limpia y carga de archivos de ejemplo."""

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from observatory.db import connect, migrate

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text() -> callable:
    """Devuelve una función que lee un archivo de ejemplo de tests/fixtures."""

    def read(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")

    return read


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    """Conexión a una base vacía y migrada; se salta si no hay TEST_DATABASE_URL."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL no está definida")
    connection = connect(database_url)
    with connection.transaction():
        connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
        connection.execute("CREATE SCHEMA public")
    migrate(connection)
    yield connection
    connection.close()
