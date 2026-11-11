-- =====================================================================
-- Precios de mercado publicados por terceros (sondeo de la Defensoría)
-- Un precio por fuente, ciudad, producto y mes.
-- =====================================================================

CREATE TABLE precio_mercado (
    fuente                  TEXT NOT NULL,             -- 'defensoria'
    ciudad                  TEXT NOT NULL,
    producto                TEXT NOT NULL,             -- coincide con producto_canonico.codigo si existe
    mes                     DATE NOT NULL CHECK (extract(day FROM mes) = 1),
    precio                  NUMERIC(12, 2) NOT NULL CHECK (precio > 0),
    presentacion_cantidad   NUMERIC(12, 3) NOT NULL CHECK (presentacion_cantidad > 0),
    presentacion_unidad     TEXT NOT NULL CHECK (presentacion_unidad IN ('g', 'ml', 'u')),
    descripcion             TEXT,                      -- texto original de la fila
    informe                 DATE NOT NULL,             -- mes del informe del que salió el valor
    verificado              BOOLEAN NOT NULL,          -- la variación publicada cuadra con los precios
    fuente_url              TEXT NOT NULL,
    PRIMARY KEY (fuente, ciudad, producto, mes)
);

ALTER TABLE precio_mercado ENABLE ROW LEVEL SECURITY;

-- =====================================================================
-- Precio de mercado por unidad base, para comparar con el supermercado
-- =====================================================================

CREATE VIEW precio_mercado_unitario WITH (security_invoker = true) AS
SELECT
    fuente,
    ciudad,
    producto,
    mes,
    precio,
    precio / presentacion_cantidad AS precio_unitario,
    presentacion_unidad AS unidad,
    verificado
FROM precio_mercado;
