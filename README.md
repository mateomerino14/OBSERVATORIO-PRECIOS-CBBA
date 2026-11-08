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
| Hipermaxi (5 sucursales de Cochabamba) | Nombre, categoría, presentación, precio, oferta y stock | Funcionando |
| Banco Central de Bolivia | Tipo de cambio oficial diario (desde 2008) | Funcionando |
| IC Norte | — | Descartada: su sitio actual solo muestra promociones y toma pedidos por WhatsApp |
| Fidalga | — | Descartada para Cochabamba: su tienda en línea es solo de Santa Cruz |

## Stack

| Capa | Tecnología |
|---|---|
| Recolección | Python 3.12, httpx, selectolax (lexbor) |
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
observatorio recolectar hipermaxi --max-paginas 5   # prueba corta
observatorio recolectar bcb                   # tipo de cambio del año en curso
observatorio recolectar bcb --anios 2025 2026 # carga histórica
pytest                                # pruebas (las de base necesitan TEST_DATABASE_URL)
ruff check . && ruff format --check .
```

## Cómo se recolecta Hipermaxi

La tienda en línea de Hipermaxi carga su catálogo desde una API pública (`/tienda-api/api/v1/public`), la misma que usa el navegador sin iniciar sesión. El recolector:

1. Busca la región de Cochabamba y sus supermercados (`markets/ciudades` y `markets/activos`).
2. Lee el árbol de categorías desde una sola página HTML de la tienda, donde Next.js lo deja embebido.
3. Para cada sucursal, pide los productos de cada subcategoría de la canasta, de 50 en 50 (`productos`).

Se recorren los rubros de alimentos, frescos, hogar, cuidado personal, frutas y granos; se dejan fuera bazar, juguetería y textiles. Si no se puede leer el árbol de categorías, se recorre el catálogo completo sin categoría.

Si la tienda responde con su verificación antibots, la corrida se detiene y queda como `bloqueada`: no se intenta saltar la protección.

## Cómo se recolecta el tipo de cambio

El BCB publica un PDF por año con la cotización oficial de cada día (`tiposDeCambioHistorico/pdf.php?anio=AAAA`). El lector ubica cada número bajo la columna de su mes por su posición en la página, porque los días sin cotización dejan celdas vacías que corren las columnas si se lee como texto plano.

- Hasta el 26 de junio de 2026 la tabla trae venta y compra; desde el 27 de junio, con el régimen flexible, un solo valor oficial, que se guarda como venta.
- Se respeta el `Crawl-delay: 10` del robots.txt del BCB.
- Cada corrida diaria vuelve a leer el año en curso, así que también recoge correcciones del BCB.

## Recolección automática

El flujo [`recolectar.yml`](.github/workflows/recolectar.yml) corre todos los días a las 07:17 (hora de Bolivia) desde `main`: aplica las migraciones pendientes, recolecta los precios de Hipermaxi y después actualiza el tipo de cambio del BCB. También se puede lanzar a mano desde *Actions → Recolección diaria → Run workflow*, con un límite de productos para probar.

Necesita el secreto `DATABASE_URL` del repositorio (*Settings → Secrets and variables → Actions*), apuntando a una base PostgreSQL accesible desde internet (por ejemplo, Supabase o Neon).

Cada corrida queda registrada en la tabla `ejecucion` con su estado (`completada`, `con_errores` o `fallida`) y la cantidad de páginas procesadas. Si fallan 20 páginas seguidas, la corrida se detiene: casi siempre significa que la tienda cambió su sitio.

## Documentación

- [`reglas.md`](reglas.md): ramas, commits y estándares de código
- [`docs/modelo-datos.md`](docs/modelo-datos.md): tablas y decisiones del modelo
