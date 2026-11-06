# Estándares de desarrollo

Observatorio de Precios CBBA — convenciones de ramas, commits y codificación.

---

## ESTÁNDARES DE RAMAS

| Rama | Uso |
|---|---|
| `main` | Versión estable; desde aquí corre la recolección diaria |
| `develop` | Integración de los módulos terminados |
| `feature/<modulo>` | Desarrollo de un módulo o funcionalidad, en `snake_case` (ej. `feature/recoleccion_hipermaxi`) |
| `fix/<tema>` | Corrección puntual sobre `develop` |
| `refactor/<tema>` | Reestructuración sin cambiar el comportamiento |
| `test/<tema>` | Pruebas nuevas o ajustes de pruebas |
| `docs/<tema>` | Documentación |

### Flujo

1. Cada módulo se desarrolla en su rama `feature/<modulo>`, creada desde `develop`.
2. Al terminarlo se abre un Pull Request hacia `develop`. Las pruebas de GitHub Actions deben pasar antes del merge.
3. Cuando `develop` reúne una entrega completa, se abre un Pull Request de `develop` hacia `main`.
4. Después del merge, la rama de trabajo se borra.

---

## ESTÁNDARES DE COMMITS

Se usa Conventional Commits.

| Tipo | Uso |
|---|---|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de errores |
| `refactor` | Reestructuración sin modificar el comportamiento |
| `docs` | Documentación |
| `test` | Creación o actualización de pruebas |
| `chore` | Configuración, dependencias, migraciones y flujos de CI |

### Formato

```
<tipo>: <Descripción>
```

### Reglas

- El mensaje comienza con mayúscula después del prefijo.
- Describe la funcionalidad, no los archivos modificados.
- Un commit representa una única funcionalidad, corrección o mejora.
- Evitar mensajes genéricos: `cambios`, `correcciones`, `actualización`.

---

## ESTÁNDARES DE CODIFICACIÓN

### Idioma

- El código fuente se escribe en inglés: módulos, funciones, variables y constantes.
- Los textos visibles para el usuario (CLI, registros, dashboard) quedan en español.
- Las tablas y columnas de la base de datos quedan en español, por corresponder al dominio.

### Comentarios

- Cada función lleva un docstring de una línea que describe su propósito.
- Dentro de las funciones solo se dejan avisos importantes, también de una línea.
- Los scripts SQL llevan un encabezado por sección y una línea donde haga falta.
- No se deja código comentado.

### Sintaxis

- El formato y el lint se validan con Ruff (`ruff check` y `ruff format`).
- No se usan expresiones condicionales (`x if c else y`) en la lógica de control; se prefieren bloques `if`/`else`.
- Se evitan valores mágicos: se declaran como constantes con nombre en mayúsculas.
- Tipado en todas las funciones públicas.

---

## RECOLECCIÓN RESPONSABLE

- Se respeta el `robots.txt` de cada tienda.
- Hay una pausa mínima de 1 segundo entre pedidos a una misma tienda.
- Solo se guardan datos públicos de catálogo: nombre, presentación, precio y disponibilidad.
- El agente se identifica con el nombre del proyecto y el enlace al repositorio.
