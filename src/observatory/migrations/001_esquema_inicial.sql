-- =====================================================================
-- Catálogo de tiendas
-- =====================================================================

CREATE TABLE cadena (
    id          SMALLSERIAL PRIMARY KEY,
    codigo      TEXT NOT NULL UNIQUE,          -- identificador estable: 'hipermaxi', 'icnorte'
    nombre      TEXT NOT NULL,
    sitio_web   TEXT NOT NULL
);

CREATE TABLE sucursal (
    id          SERIAL PRIMARY KEY,
    cadena_id   SMALLINT NOT NULL REFERENCES cadena (id),
    codigo      TEXT NOT NULL,                 -- como aparece en la URL de la tienda
    nombre      TEXT NOT NULL,
    ciudad      TEXT NOT NULL,
    id_externo  TEXT,                          -- id de la sucursal en el sistema de la cadena
    direccion   TEXT,
    UNIQUE (cadena_id, codigo)
);

-- =====================================================================
-- Productos tal como los publica cada cadena
-- =====================================================================

CREATE TABLE producto (
    id                  SERIAL PRIMARY KEY,
    cadena_id           SMALLINT NOT NULL REFERENCES cadena (id),
    codigo_externo      TEXT NOT NULL,         -- código del producto en la tienda
    nombre              TEXT NOT NULL,
    marca               TEXT,
    contenido_cantidad  NUMERIC(12, 3),        -- presentación normalizada: 5 kg -> 5000 g
    contenido_unidad    TEXT CHECK (contenido_unidad IN ('g', 'ml', 'u')),
    vendido_por_peso    BOOLEAN NOT NULL DEFAULT false,  -- el precio es por kilo
    categoria           TEXT,
    subcategoria        TEXT,
    url                 TEXT NOT NULL,
    primera_vez         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultima_vez          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cadena_id, codigo_externo)
);

CREATE INDEX producto_categoria_idx ON producto (cadena_id, categoria, subcategoria);

-- =====================================================================
-- Precios: una observación por producto, sucursal y día
-- =====================================================================

CREATE TABLE observacion_precio (
    producto_id     INTEGER NOT NULL REFERENCES producto (id),
    sucursal_id     INTEGER NOT NULL REFERENCES sucursal (id),
    fecha           DATE NOT NULL,             -- día en hora de Bolivia
    precio          NUMERIC(12, 2) NOT NULL CHECK (precio > 0),
    precio_regular  NUMERIC(12, 2) CHECK (precio_regular > 0),  -- antes del descuento, si hay oferta
    disponible      BOOLEAN NOT NULL,
    existencias     INTEGER,                   -- unidades visibles; NULL si la tienda no las muestra
    capturado_en    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (producto_id, sucursal_id, fecha)
);

CREATE INDEX observacion_precio_fecha_idx ON observacion_precio (fecha);

-- =====================================================================
-- Emparejamiento: el mismo producto en distintas cadenas
-- =====================================================================

CREATE TABLE producto_canonico (
    id                  SERIAL PRIMARY KEY,
    nombre              TEXT NOT NULL,
    categoria           TEXT NOT NULL,         -- rubro de la canasta: 'arroz', 'aceite', 'leche'
    contenido_cantidad  NUMERIC(12, 3) NOT NULL,
    contenido_unidad    TEXT NOT NULL CHECK (contenido_unidad IN ('g', 'ml', 'u')),
    en_canasta          BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE emparejamiento (
    producto_id             INTEGER PRIMARY KEY REFERENCES producto (id),
    producto_canonico_id    INTEGER NOT NULL REFERENCES producto_canonico (id),
    metodo                  TEXT NOT NULL CHECK (metodo IN ('manual', 'automatico')),
    confianza               NUMERIC(4, 3) CHECK (confianza BETWEEN 0 AND 1),
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- Tipo de cambio
-- =====================================================================

CREATE TABLE tipo_cambio (
    fecha   DATE NOT NULL,
    fuente  TEXT NOT NULL CHECK (fuente IN ('bcb_oficial', 'paralelo')),
    compra  NUMERIC(8, 4),
    venta   NUMERIC(8, 4) NOT NULL,
    PRIMARY KEY (fecha, fuente)
);

-- =====================================================================
-- Registro de cada corrida de recolección
-- =====================================================================

CREATE TABLE ejecucion (
    id              SERIAL PRIMARY KEY,
    fuente          TEXT NOT NULL,
    iniciada_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    terminada_en    TIMESTAMPTZ,
    estado          TEXT NOT NULL DEFAULT 'en_curso'
                    CHECK (estado IN ('en_curso', 'completada', 'con_errores', 'fallida',
                                      'bloqueada')),
    paginas_ok      INTEGER NOT NULL DEFAULT 0,
    paginas_error   INTEGER NOT NULL DEFAULT 0,
    observaciones   INTEGER NOT NULL DEFAULT 0,   -- precios guardados en la corrida
    detalle         TEXT
);

-- =====================================================================
-- Datos base
-- =====================================================================

INSERT INTO cadena (codigo, nombre, sitio_web) VALUES
    ('hipermaxi', 'Hipermaxi', 'https://www.hipermaxi.com'),
    ('icnorte', 'IC Norte', 'https://www.icnorte.com'),
    ('fidalga', 'Fidalga', 'https://www.fidalga.com');
