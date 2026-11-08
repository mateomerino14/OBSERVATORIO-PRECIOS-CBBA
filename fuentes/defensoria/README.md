# Precios de mercado de la Defensoría del Pueblo

`cochabamba.csv` tiene los precios de mercado de Cochabamba publicados en el **Sondeo de Precios de Productos de Consumo General** de la Defensoría del Pueblo: 21 productos, de agosto de 2024 a diciembre de 2025 (16 meses; septiembre de 2024 no se publicó). Los mercados relevados en Cochabamba incluyen el 25 de Mayo.

## Cómo se generó

1. Se descargaron los 14 informes mensuales publicados en `defensoria.gob.bo` (noviembre de 2024 a diciembre de 2025). No hay informes mensuales de 2026 publicados.
2. `scripts/extraer_defensoria.py` convierte cada PDF a texto con `pdftotext -layout` y lee la tabla de Cochabamba (`observatory/sources/defensoria.py`).
3. Cada mes aparece en dos informes: como mes del informe y como mes anterior en el siguiente. Se toma el del propio mes; si falta, el del siguiente. En 188 de 224 meses repetidos los valores son idénticos; el resto difiere solo por redondeo.

```bash
python scripts/extraer_defensoria.py <carpeta_con_los_pdf> fuentes/defensoria/cochabamba.csv
observatorio importar defensoria fuentes/defensoria/cochabamba.csv
```

## Columnas

| Columna | Contenido |
|---|---|
| `mes` | Mes del precio (AAAA-MM) |
| `producto` | Código del producto; coincide con el de la canasta cuando existe |
| `precio` | Precio en Bs por la presentación de la Defensoría |
| `presentacion_cantidad`, `presentacion_unidad` | Presentación en unidad base (g, ml, u) |
| `descripcion` | Texto original de la fila en el informe |
| `informe` | Informe del que salió el valor |
| `variacion_verificada` | La variación % publicada cuadra con los precios leídos |
| `fuente_url` | PDF de origen |

## Validación

- Con estos precios y las cantidades de la canasta de la Defensoría, el costo de la canasta de Cochabamba da **Bs 171,59 en enero de 2025 y Bs 247,91 en diciembre de 2025**; la Defensoría publicó Bs 171 y Bs 247. Hay una prueba automática que lo verifica.
- 11 de 334 filas no cuadran con la variación publicada (sobre todo productos de menos de Bs 2, donde el redondeo a un decimal descuadra el porcentaje). Se conservan, marcadas.

## Supuestos

- 1 libra = 460 g.
- 1 cuartilla (cebolla y zanahoria) = 6 libras = 2.760 g. No es un dato publicado: es el valor con el que los precios reproducen el costo de canasta oficial.
- Informes sin año en el nombre del archivo (`...-agosto.pdf`) corresponden a 2025.

## Advertencias

Es un sondeo en mercados, no un índice: los precios de un mes a otro pueden moverse por cambio de puesto o de calidad. Ejemplos: el azúcar pasa de Bs 4,10 a 12,48 la libra entre noviembre y diciembre de 2025, y la cebolla salta 133 % entre marzo y abril de 2025. Conviene leer tendencias de varios meses, no variaciones mensuales sueltas.
