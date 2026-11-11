# Canasta

El observatorio mide el costo diario de la **canasta básica de alimentos de la Defensoría del Pueblo**: 13 productos, consumo semanal de una familia de cuatro personas. La Defensoría la mide cada mes en los mercados de las capitales; aquí se mide cada día en las sucursales de Hipermaxi de Cochabamba, para poder comparar supermercado y mercado.

La definición está en [`canastas/defensoria_semanal.toml`](../canastas/defensoria_semanal.toml).

## Cómo se calcula

1. **Emparejamiento.** Cada producto de la canasta (producto canónico) tiene reglas: expresiones que el nombre debe contener o no, subcategorías de la tienda y límites de presentación. `observatorio canasta cargar` aplica las reglas a todos los productos de tienda y guarda el resultado en `emparejamiento`. Los emparejamientos hechos a mano (`metodo = 'manual'`) se respetan.
2. **Precio por unidad base.** Para cada producto canónico, sucursal y día, la vista `precio_canonico_diario` calcula el precio por gramo, mililitro o unidad de todos los productos emparejados y disponibles: la **mediana** (precio típico) y el **mínimo** (lo más barato).
3. **Costo de la canasta.** La vista `costo_canasta_diario` multiplica cada cantidad por ese precio y suma:
   - `costo_tipico`: con la mediana de cada producto.
   - `costo_economico`: comprando siempre lo más barato.
   - `items_con_precio / items_total`: cuántos productos de la canasta tuvieron precio ese día.

## Cantidades

| Producto | Defensoría | Cantidad usada |
|---|---|---|
| Papaya mediana | 1 unidad | 1.500 g |
| Plátano mediano | 12 unidades | 1.800 g |
| Cebolla | 2 libras | 920 g |
| Tomate | 2 libras | 920 g |
| Zanahoria | 2 libras | 920 g |
| Azúcar blanca | 1 libra | 460 g |
| Arroz de primera | 2 libras | 920 g |
| Harina de trigo | 2 libras | 920 g |
| Fideo | 1 libra | 460 g |
| Pulpa de res | 1 kg | 1.000 g |
| Pollo entero | 2 kg | 2.000 g |
| Leche fluida | 1 bolsa | 946 ml |
| Huevos medianos | 10 unidades | 10 u |

**Supuestos:** 1 libra = 460 g (la de los mercados bolivianos); papaya mediana = 1,5 kg; plátano mediano = 150 g.

## Decisiones y limitaciones

- **Frutas y verduras.** No todas las sucursales publican frescos en línea. El 11 de noviembre de 2026, Circunvalación, Juan de la Rosa y Sacaba tenían papaya, cebolla, tomate y zanahoria (12 de 13 productos); Blanco Galindo y Panamericana, ninguno (8 de 13). El plátano (banano) no aparece en ninguna: solo hay plátano de freír, que es otro producto y se excluye.
- **Costo de la ciudad y de cada sucursal.** El costo de la ciudad junta los productos de todas las sucursales, ítem por ítem, así que tiene precio para un producto aunque solo una sucursal lo venda. Entre sucursales se compara solo sobre los productos que tienen todas ese día; si no, una sucursal con más productos en línea parecería más cara.
- **Pulpa de res.** Hipermaxi no usa ese nombre; se toman los cortes sin hueso equivalentes (cuadrada, bollo chico y grande, peceto especial), sin la carne al vacío, que es otro segmento de precio.
- **Leche fluida.** Solo leche entera o natural en bolsa (800–1.000 ml); se excluyen cajas UHT, larga vida y leches con sabor.
- **Huevos medianos.** La Defensoría cotiza huevo mediano por unidad. Se excluyen los que dicen otro tamaño en el nombre (pequeño, grande, extra grande): el pequeño, el más barato, fijaba el costo económico con un huevo más chico. Los que no dicen tamaño son el huevo común del súper y se mantienen. También entran los packs.
- **Bolsas al por mayor.** Se excluyen presentaciones mayores a 5 kg (harina y fideo de 11,34 kg), que bajarían artificialmente el precio por kilo.
- **Productos agotados.** No cuentan para el precio del día.
