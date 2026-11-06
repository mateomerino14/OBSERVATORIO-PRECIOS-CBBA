# Archivos de ejemplo

Las páginas de Hipermaxi de esta carpeta están **armadas a mano** a partir de lo que muestra públicamente el sitio (título, descripción, "Disponibilidad", "Precio por UNIDAD" y el bloque JSON-LD con `offers`). Sirven para fijar el comportamiento del parser.

Cuando el entorno de desarrollo tenga acceso a `hipermaxi.com`, se reemplazan por páginas reales guardadas con `curl` y se ajusta el parser si hace falta. El nombre de cada archivo real debe llevar la fecha de captura (ej. `hipermaxi_producto_2026-11-07.html`).
