"""Configuración leída de variables de entorno."""

import os
from dataclasses import dataclass

DEFAULT_DELAY_SECONDS = 1.5


class MissingSettingError(RuntimeError):
    """Falta una variable de entorno obligatoria."""


@dataclass(frozen=True)
class Settings:
    """Valores de configuración de una corrida."""

    database_url: str
    delay_seconds: float


def load_settings() -> Settings:
    """Lee la configuración del entorno; DATABASE_URL es obligatoria."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise MissingSettingError("Falta la variable DATABASE_URL (ver .env.example)")
    delay = float(os.environ.get("PAUSA_SEGUNDOS", DEFAULT_DELAY_SECONDS))
    return Settings(database_url=database_url, delay_seconds=delay)
