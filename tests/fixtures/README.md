# Archivos de ejemplo

Archivos reales de las fuentes, recortados para que las pruebas sean livianas.

| Archivo | Origen |
|---|---|
| `bcb_tipo_cambio_2025.pdf`, `bcb_tipo_cambio_2026.pdf` | PDF anual de tipos de cambio del BCB (`tiposDeCambioHistorico/pdf.php?anio=AAAA`); el de 2026 trae el cambio de régimen del 27 de junio |
| `defensoria_AAAA-MM.txt` | Texto (`pdftotext -layout`) de cuatro informes mensuales de la Defensoría: tablas de dos y de cinco meses, nombres partidos en dos líneas, el final de la tabla de Cochabamba y una variación calculada contra el primer mes |
| `hipermaxi_api_ciudades.json` (Hipermaxi, 6 nov 2026) | `GET /tienda-api/api/v1/public/markets/ciudades` |
| `hipermaxi_api_sucursales.json` | `GET .../markets/activos?IdMarket=0&IdTipoServicio=1`, solo Cochabamba y dos de Santa Cruz, con los campos que se usan |
| `hipermaxi_api_productos.json` | `GET .../productos` de la subcategoría Aderezos de Blanco Galindo, primeros 5 productos |
| `hipermaxi_categoria.html` | Página de categoría Abarrotes, solo el script de Next.js que trae el árbol de categorías |

Si la tienda cambia su formato, se capturan respuestas nuevas, se reemplazan aquí y se ajusta el parser.
