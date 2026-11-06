# Observatorio de Precios CBBA

Seguimiento diario de los precios de la canasta familiar en supermercados de Cochabamba, y de cómo se relacionan con el tipo de cambio desde la liberación del dólar en junio de 2026.

> Estado: en construcción. Primera fuente: Hipermaxi Cochabamba.

## Preguntas que busca responder

- ¿Cuánto subió la canasta familiar en supermercados desde el cambio de régimen cambiario?
- ¿Qué productos trasladan antes la devaluación: los importados o los nacionales?
- ¿Qué cadena y qué sucursal son más caras para la misma canasta?

## Fuentes

| Fuente | Qué se toma | Estado |
|---|---|---|
| Hipermaxi (sucursales de Cochabamba) | Nombre, presentación, precio y disponibilidad | En desarrollo |
| IC Norte | Catálogo y precios | Pendiente |
| Fidalga | Catálogo y precios | Pendiente de confirmar cobertura en Cochabamba |
| Banco Central de Bolivia | Tipo de cambio oficial diario | Pendiente |

## Stack

| Capa | Tecnología |
|---|---|
| Recolección | Python 3.12, httpx, selectolax |
| Datos | PostgreSQL con migraciones versionadas |
| Programación | GitHub Actions con cron diario |
| Calidad | pytest (con PostgreSQL real), Ruff |

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                  # ajustar DATABASE_URL
observatorio migrar                   # crea o actualiza las tablas
observatorio recolectar hipermaxi     # recolecta los precios del día
pytest                                # pruebas (las de base necesitan TEST_DATABASE_URL)
ruff check . && ruff format --check .
```

## Documentación

- [`reglas.md`](reglas.md): ramas, commits y estándares de código
- [`docs/modelo-datos.md`](docs/modelo-datos.md): tablas y decisiones del modelo
