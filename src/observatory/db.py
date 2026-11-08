"""Conexión a PostgreSQL y migraciones versionadas."""

from importlib import resources

import psycopg

MIGRATIONS_PACKAGE = "observatory.migrations"

CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS migracion_aplicada (
    version     TEXT PRIMARY KEY,
    aplicada_en TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def connect(database_url: str) -> psycopg.Connection:
    """Abre una conexión con zona horaria de Bolivia para que las fechas salgan en hora local."""
    connection = psycopg.connect(database_url)
    connection.execute("SET TIME ZONE 'America/La_Paz'")
    connection.commit()
    return connection


def list_migrations() -> list[tuple[str, str]]:
    """Devuelve las migraciones del paquete ordenadas por versión, como (versión, SQL)."""
    files = resources.files(MIGRATIONS_PACKAGE).iterdir()
    scripts = [item for item in files if item.name.endswith(".sql")]
    scripts.sort(key=lambda item: item.name)
    return [(item.name.removesuffix(".sql"), item.read_text(encoding="utf-8")) for item in scripts]


def migrate(connection: psycopg.Connection) -> list[str]:
    """Aplica las migraciones pendientes, cada una en su propia transacción."""
    with connection.transaction():
        connection.execute(CREATE_MIGRATIONS_TABLE)
    applied = {row[0] for row in connection.execute("SELECT version FROM migracion_aplicada")}
    newly_applied = []
    for version, sql in list_migrations():
        if version in applied:
            continue
        with connection.transaction():
            connection.execute(sql)
            connection.execute("INSERT INTO migracion_aplicada (version) VALUES (%s)", (version,))
        newly_applied.append(version)
    return newly_applied
