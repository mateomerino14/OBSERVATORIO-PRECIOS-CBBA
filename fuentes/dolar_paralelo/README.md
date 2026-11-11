# Dólar paralelo: cierres mensuales

`cierres_mensuales.csv` tiene una cotización de venta del dólar paralelo por mes, de agosto de 2024 a diciembre de 2025. No hay una fuente oficial del paralelo; la serie se armó a partir de los boletines semanales del **CEED de CADECOCRUZ** (Cámara de la Construcción de Santa Cruz), que lo publican con datos de plataformas de cambio digital.

## Cómo se calculó

Cada boletín trae el valor del día como **TOTAL**: variación porcentual sobre el tipo de cambio fijo de Bs 6,97.

| Período | Método (`metodo`) |
|---|---|
| Ago – nov 2024 | `a_12_meses`: valor del boletín ÷ (1 + variación a 12 meses). Da el valor del mismo día un año antes, cercano al cierre del mes. |
| Dic 2024 | `acumulada_anual`: valor del 21-10-2025 ÷ (1 + acumulada 2025 a esa fecha). |
| Ene – nov 2025 | `variacion_mensual`: cierre anterior × (1 + variación mensual definitiva publicada en el CEED 52). |
| Dic 2025 | `acumulada_anual`: cierre 2024 × (1 − 13,07 %), variación de 2025 publicada en el CEED 54. |

`fecha_dato` es el día en que se midió el valor; en la base cada cierre se guarda con el último día de su mes (`tipo_cambio`, fuente `paralelo`).

## Verificaciones

- El cierre de septiembre de 2025 encadenado (Bs 12,62) coincide con el valor del boletín del 30-09-2025.
- Agosto de 2024 da Bs 11,22 desde dos boletines distintos (19 y 25 de agosto de 2025).
- El cierre de 2025 (Bs 9,66) coincide con el reportado en prensa (Bs 9,60).
- El máximo es mayo de 2025 (Bs 16,39), como reportan todas las fuentes.

## Limitaciones

- Es una serie aproximada: cada fuente mide el paralelo distinto (casas de cambio, Binance, otras plataformas). Por ejemplo, la prensa publicó Bs 16,50 el 30-06-2025, frente a Bs 14,96 de esta serie.
- Un valor por mes: sirve para comparar con precios mensuales, no para movimientos diarios.
- El boletín CEED 50 publicó "acumulada 2025: 5,23 %" donde sus otros datos implican −5,23 %; por eso se usa siempre el TOTAL, que es consistente entre boletines.
