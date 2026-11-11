# Modelos

Dos modelos ayudan a revisar los datos. Ninguno cambia un precio ni una regla por su cuenta: señalan qué mirar y una persona decide. Sus resultados se ven en la pantalla **Modelos** del sitio.

## 1. Sugerencias de emparejamiento

**Problema.** Las reglas de [`canastas/defensoria_semanal.toml`](../canastas/defensoria_semanal.toml) deciden qué productos de Hipermaxi cuentan para cada ítem de la canasta. Son precisas pero frágiles: un producto nuevo con otro nombre ("Pack Huevo de Oro 12 un") o en otra subcategoría queda fuera sin que nadie lo note.

**Método** ([`src/observatory/suggest.py`](../src/observatory/suggest.py)):

1. Cada nombre se limpia: minúsculas, sin tildes, sin cantidades ni palabras de presentación (`5 kg`, `bolsa`, `pack`).
2. Se representa con **TF-IDF de n-gramas de 3 a 5 caracteres**. Los n-gramas toleran abreviaturas, plurales y mayúsculas ("FIDEOS", "Fideo"). La subcategoría de la tienda se suma con poco peso (15 %).
3. Cada ítem tiene un **prototipo**: el promedio de los vectores de los productos que sus reglas ya aceptan. Si no acepta ninguno, el prototipo es el nombre del ítem.
4. Se ordenan los productos sin emparejar de la misma unidad (g, ml o u) por **similitud coseno** con el prototipo.
5. El **umbral** de cada ítem sale de sus propios datos: el percentil 10 de la similitud de cada producto aceptado con el prototipo armado sin él (dejando uno fuera). Un candidato se sugiere si se parece al grupo al menos tanto como los aceptados menos típicos. Sin al menos 3 aceptados, el umbral es 0,50.
6. Para cada candidato se explica qué regla lo deja fuera: el nombre, la subcategoría o la presentación. Lo que una regla **excluye a propósito** (arroz integral, salsa de tomate) no se vuelve a sugerir.
7. También se listan los **aceptados poco parecidos al resto**, que pueden ser errores de la regla.

**Evaluación.** Se toma cada producto que las reglas aceptan, se arma el prototipo sin él y se cuenta en qué puesto queda entre todos los productos sin emparejar de su unidad. El sitio muestra qué proporción queda entre los 10 primeros: el 11 de noviembre de 2026, con 14.288 productos de las 5 sucursales, 121 de 141 (86 %), con puesto mediano 2.

**Qué encontró.** En noviembre de 2026, el modelo señaló:

- Tres packs de huevos ("Pack Huevo de Oro 12 un") que la regla dejaba fuera porque el nombre no empieza con "huevo". Ahora entran.
- Dos pastas especiales aceptadas como fideo corto: "Penne Libre Gluten" y "Fideos de Garbanzo". Su precio no es comparable con el fideo común. Ahora se excluyen junto con las de lenteja y quinua.
- Ya con los datos de producción: "Fetuccini" escrito con una sola t, que la exclusión de pastas largas no cubría, y fideos instantáneos "Yakissoba".

También sugiere cortes "especiales" de res para la pulpa (picaña, cuadril) porque el nombre se parece. Son otro producto y se descartan: por eso las sugerencias se revisan a mano.

```bash
observatorio canasta sugerir canastas/defensoria_semanal.toml
```

## 2. Precios anómalos

**Problema.** Un salto de precio puede ser real (la cebolla en una mala cosecha), un error de carga del sondeo o el reflejo de algo que movió a todos los precios (el dólar). Solo los dos primeros son anomalías.

**Mercado, mensual** ([`src/observatory/anomalies.py`](../src/observatory/anomalies.py)):

1. Cambio de cada producto entre meses consecutivos, en logaritmo.
2. Se le resta el **cambio mediano de todos los productos ese mes**. Lo que queda es el movimiento propio del producto, sin la inflación ni el dólar.
3. Ese residuo se compara con la historia del mismo producto con el **z-score modificado** (mediana y MAD en lugar de media y desvío, para que los propios saltos no inflen la escala).
4. Se marca |z| ≥ 3,5, el umbral habitual de Iglewicz y Hoaglin, si además el residuo es de al menos 10 %. En series muy estables la MAD es casi cero y cualquier centésimo daría un z enorme.

Entre agosto de 2024 y diciembre de 2025 marca 11 de 294 cambios mensuales. Por ejemplo, la cebolla subió 140 % en diciembre de 2025 cuando el resto de la canasta subió 2 %. La carne molida cae 27 % en febrero de 2025 y sube 48 % en marzo: una baja seguida de una subida parecida suele ser un error del sondeo, no un cambio real.

**Supermercado, diario.** Para los productos de la canasta, se compara el precio del último día con la **mediana de los días anteriores** del mismo producto en la misma sucursal, en una ventana de 14 días. Se marca un cambio de 20 % o más con al menos 7 días previos, e indica si el producto está en oferta, porque una oferta explica una bajada. Se activa solo cuando la recolección diaria junta 8 días.

## Límites

- La similitud de texto no entiende de productos: "Picaña Especial" se parece a "Peceto Especial". Por eso sugiere y no decide.
- El modelo solo ve el nombre y la subcategoría; no ve la foto ni la descripción de la tienda.
- El sondeo de la Defensoría tiene pocos meses (16) y es ruidoso: una anomalía de mercado es una pista para revisar, no una conclusión.
