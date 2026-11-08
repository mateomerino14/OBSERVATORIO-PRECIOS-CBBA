-- =====================================================================
-- Producto canónico: se identifica por código y mide en una unidad base
-- =====================================================================

ALTER TABLE producto_canonico
    DROP COLUMN en_canasta,
    DROP COLUMN contenido_cantidad,
    ADD COLUMN codigo TEXT;

ALTER TABLE producto_canonico RENAME COLUMN contenido_unidad TO unidad;
ALTER TABLE producto_canonico ALTER COLUMN codigo SET NOT NULL;
ALTER TABLE producto_canonico ADD CONSTRAINT producto_canonico_codigo_key UNIQUE (codigo);

-- =====================================================================
-- Canastas y sus cantidades por producto canónico
-- =====================================================================

CREATE TABLE canasta (
    id          SERIAL PRIMARY KEY,
    codigo      TEXT NOT NULL UNIQUE,
    nombre      TEXT NOT NULL,
    descripcion TEXT,
    referencia  TEXT,                              -- fuente de la canasta (URL)
    personas    SMALLINT NOT NULL CHECK (personas > 0),
    periodo     TEXT NOT NULL CHECK (periodo IN ('semanal', 'mensual'))
);

CREATE TABLE canasta_item (
    canasta_id              INTEGER NOT NULL REFERENCES canasta (id) ON DELETE CASCADE,
    producto_canonico_id    INTEGER NOT NULL REFERENCES producto_canonico (id),
    cantidad                NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),  -- en g, ml o u
    PRIMARY KEY (canasta_id, producto_canonico_id)
);

ALTER TABLE canasta ENABLE ROW LEVEL SECURITY;
ALTER TABLE canasta_item ENABLE ROW LEVEL SECURITY;

-- =====================================================================
-- Precio por unidad base de cada producto canónico, por sucursal y día.
-- Solo productos disponibles y con presentación conocida.
-- =====================================================================

CREATE VIEW precio_canonico_diario WITH (security_invoker = true) AS
SELECT
    o.fecha,
    o.sucursal_id,
    e.producto_canonico_id,
    count(*) AS productos,
    min(o.precio / p.contenido_cantidad) AS precio_unitario_minimo,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY o.precio / p.contenido_cantidad)
        AS precio_unitario_mediana
FROM observacion_precio o
JOIN producto p ON p.id = o.producto_id
JOIN emparejamiento e ON e.producto_id = p.id
JOIN producto_canonico pc ON pc.id = e.producto_canonico_id
WHERE o.disponible
  AND p.contenido_cantidad > 0
  AND p.contenido_unidad = pc.unidad
GROUP BY o.fecha, o.sucursal_id, e.producto_canonico_id;

-- =====================================================================
-- Costo de cada canasta por sucursal y día: con el precio mediano
-- (típico) y con el más barato de cada producto (canasta económica).
-- =====================================================================

CREATE VIEW costo_canasta_diario WITH (security_invoker = true) AS
SELECT
    c.codigo AS canasta,
    pcd.fecha,
    pcd.sucursal_id,
    round(sum(ci.cantidad * pcd.precio_unitario_mediana)::numeric, 2) AS costo_tipico,
    round(sum(ci.cantidad * pcd.precio_unitario_minimo)::numeric, 2) AS costo_economico,
    count(*) AS items_con_precio,
    (SELECT count(*) FROM canasta_item total WHERE total.canasta_id = c.id) AS items_total
FROM canasta c
JOIN canasta_item ci ON ci.canasta_id = c.id
JOIN precio_canonico_diario pcd ON pcd.producto_canonico_id = ci.producto_canonico_id
GROUP BY c.id, c.codigo, pcd.fecha, pcd.sucursal_id;
