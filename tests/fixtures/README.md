# Archivos de ejemplo

Respuestas reales de Hipermaxi capturadas el 6 de noviembre de 2026, recortadas para que las pruebas sean livianas.

| Archivo | Origen |
|---|---|
| `hipermaxi_api_ciudades.json` | `GET /tienda-api/api/v1/public/markets/ciudades` |
| `hipermaxi_api_sucursales.json` | `GET .../markets/activos?IdMarket=0&IdTipoServicio=1`, solo Cochabamba y dos de Santa Cruz, con los campos que se usan |
| `hipermaxi_api_productos.json` | `GET .../productos` de la subcategoría Aderezos de Blanco Galindo, primeros 5 productos |
| `hipermaxi_categoria.html` | Página de categoría Abarrotes, solo el script de Next.js que trae el árbol de categorías |

Si la tienda cambia su formato, se capturan respuestas nuevas, se reemplazan aquí y se ajusta el parser.
