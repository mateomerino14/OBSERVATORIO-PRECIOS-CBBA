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
| Dólar paralelo (CEED de CADECOCRUZ) | Cierre mensual aproximado (ago 2024 – dic 2025) | Cargado ([detalle](fuentes/dolar_paralelo/README.md)) |
| Defensoría del Pueblo | Precios de mercado mensuales de 21 alimentos en Cochabamba (ago 2024 – dic 2025) | Cargado ([detalle](fuentes/defensoria/README.md)) |
| IC Norte | — | Descartada: su sitio actual solo muestra promociones y toma pedidos por WhatsApp |
| Fidalga | — | Descartada para Cochabamba: su tienda en línea es solo de Santa Cruz |

## Stack

| Capa | Tecnología |
|---|---|
| Recolección | Python 3.12, httpx, selectolax (lexbor) |
| Datos | PostgreSQL con migraciones versionadas |
| Programación | GitHub Actions con cron diario |
| Dashboard | Vite, React, TypeScript, gráficos SVG propios; GitHub Pages |
| Calidad | pytest (con PostgreSQL real), Ruff, Vitest y Testing Library |

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
observatorio importar defensoria fuentes/defensoria/cochabamba.csv  # precios de mercado
observatorio importar paralelo fuentes/dolar_paralelo/cierres_mensuales.csv
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

## Canasta

El costo diario se mide sobre la canasta básica de alimentos de la Defensoría del Pueblo (13 productos, familia de cuatro, una semana), para compararla con el sondeo mensual que la Defensoría hace en mercados. Cada producto de la canasta se empareja con los productos de la tienda mediante reglas en [`canastas/defensoria_semanal.toml`](canastas/defensoria_semanal.toml), y las vistas `precio_canonico_diario` y `costo_canasta_diario` calculan el precio típico (mediana) y el económico (mínimo).

```bash
observatorio canasta revisar canastas/defensoria_semanal.toml   # qué producto quedó en cada ítem
```

Detalle, supuestos y limitaciones en [`docs/canasta.md`](docs/canasta.md).

## Dashboard

Sitio estático en [`web/`](web) (Vite, React y TypeScript) con cuatro pantallas: resumen, súper vs. mercado, productos y fuentes. No consulta la base: `observatorio exportar` genera un JSON con todo lo que muestra, y el flujo [`sitio.yml`](.github/workflows/sitio.yml) lo construye y publica en GitHub Pages después de cada recolección diaria.

```bash
observatorio exportar --canasta canastas/defensoria_semanal.toml --salida web/public/data/dashboard.json
cd web && npm install && npm run dev   # http://localhost:5173
npm test                               # pruebas del sitio
```

## Carga histórica

Los datos que no se recolectan a diario (tipo de cambio de años anteriores, precios de la Defensoría y dólar paralelo) se cargan con el flujo [`cargar-historico.yml`](.github/workflows/cargar-historico.yml), que se lanza a mano desde *Actions → Carga histórica → Run workflow*. Es idempotente.

## Documentación

- [`reglas.md`](reglas.md): ramas, commits y estándares de código
- [`docs/modelo-datos.md`](docs/modelo-datos.md): tablas y decisiones del modelo
- [`docs/canasta.md`](docs/canasta.md): cómo se calcula el costo de la canasta
