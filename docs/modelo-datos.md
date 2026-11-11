# Modelo de datos

```
cadena 1──* sucursal
cadena 1──* producto 1──* observacion_precio *──1 sucursal
producto *──1 producto_canonico      (a través de emparejamiento)
canasta 1──* canasta_item *──1 producto_canonico
tipo_cambio                          (independiente; se cruza por fecha)
ejecucion                            (registro de cada corrida)
```

## Tablas

| Tabla | Qué guarda |
|---|---|
| `cadena` | Supermercados: Hipermaxi se recolecta; IC Norte y Fidalga quedan registradas pero se descartaron como fuente (ver README) |
| `sucursal` | Sucursales de cada cadena, con su ciudad |
| `producto` | Productos tal como los publica cada cadena, con la presentación normalizada |
| `observacion_precio` | Un precio por producto, sucursal y día |
| `producto_canonico` | Producto genérico de una canasta (ej. arroz de primera), con su unidad base |
| `emparejamiento` | Qué producto de tienda corresponde a cuál canónico (por reglas o a mano) |
| `canasta` / `canasta_item` | Canastas y la cantidad de cada producto canónico |
| Vista `precio_canonico_diario` | Precio por unidad base (mediana y mínimo) por producto canónico, sucursal y día |
| `tipo_cambio` | Tipo de cambio diario: oficial del BCB y paralelo |
| `precio_mercado` | Precios mensuales de mercado publicados por terceros (Defensoría), con su informe de origen |
| Vista `precio_mercado_unitario` | Precio de mercado por unidad base, para comparar con el supermercado |
| `ejecucion` | Inicio, fin, estado y conteos de cada recolección |

## Decisiones

- **Una observación por día.** La clave es `(producto, sucursal, fecha)`. Si la recolección corre dos veces el mismo día, queda la última captura. Así el historial es una serie diaria limpia y la recolección se puede repetir sin duplicar.
- **Fecha en hora de Bolivia.** La conexión fija `America/La_Paz`, para que una captura a las 23:30 no caiga en el día siguiente por estar en UTC.
- **Presentación normalizada.** "5 kg", "5 Kl" y "5000 gr" se guardan como `5000 g`; "3 Lts" como `3000 ml`. Esto permite comparar precio por kilo o por litro entre cadenas.
- **Producto de tienda y producto canónico separados.** Cada cadena nombra distinto el mismo producto. Se guardan tal cual y se enlazan a un canónico con reglas versionadas (`metodo = 'regla'`) o a mano (`metodo = 'manual'`); el modelo de sugerencias ([`docs/modelos.md`](modelos.md)) ayuda a revisar las reglas.
- **El costo de la canasta se calcula en la exportación.** La base guarda precios por unidad (`precio_canonico_diario`); juntar sucursales o compararlas sobre ítems comunes es una decisión de presentación y vive en `export.py`. La vista `costo_canasta_diario` se quitó en la migración 005 porque sumaba por sucursal solo los ítems que cada una tenía.
- **`precio_regular`.** Se guarda cuando hay oferta, para distinguir una baja de precio real de una promoción.
- **`existencias`.** Hipermaxi muestra unidades disponibles por sucursal; se guardan porque sirven para detectar desabastecimiento.
