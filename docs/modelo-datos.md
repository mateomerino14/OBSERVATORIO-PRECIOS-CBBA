# Modelo de datos

```
cadena 1──* sucursal
cadena 1──* producto 1──* observacion_precio *──1 sucursal
producto *──1 producto_canonico      (a través de emparejamiento)
tipo_cambio                          (independiente; se cruza por fecha)
ejecucion                            (registro de cada corrida)
```

## Tablas

| Tabla | Qué guarda |
|---|---|
| `cadena` | Supermercados seguidos: Hipermaxi, IC Norte, Fidalga |
| `sucursal` | Sucursales de cada cadena, con su ciudad |
| `producto` | Productos tal como los publica cada cadena, con la presentación normalizada |
| `observacion_precio` | Un precio por producto, sucursal y día |
| `producto_canonico` | El "mismo" producto entre cadenas (ej. Aceite Fino 900 ml) |
| `emparejamiento` | Qué producto de cada cadena corresponde a cuál canónico |
| `tipo_cambio` | Tipo de cambio diario: oficial del BCB y paralelo |
| `ejecucion` | Inicio, fin, estado y conteos de cada recolección |

## Decisiones

- **Una observación por día.** La clave es `(producto, sucursal, fecha)`. Si la recolección corre dos veces el mismo día, queda la última captura. Así el historial es una serie diaria limpia y la recolección se puede repetir sin duplicar.
- **Fecha en hora de Bolivia.** La conexión fija `America/La_Paz`, para que una captura a las 23:30 no caiga en el día siguiente por estar en UTC.
- **Presentación normalizada.** "5 kg", "5 Kl" y "5000 gr" se guardan como `5000 g`; "3 Lts" como `3000 ml`. Esto permite comparar precio por kilo o por litro entre cadenas.
- **Producto de tienda y producto canónico separados.** Cada cadena nombra distinto el mismo producto. Se guardan tal cual y se enlazan a un canónico aparte, primero a mano para la canasta y después con emparejamiento automático.
- **`precio_regular`.** Se guarda cuando hay oferta, para distinguir una baja de precio real de una promoción.
- **`existencias`.** Hipermaxi muestra unidades disponibles por sucursal; se guardan porque sirven para detectar desabastecimiento.
