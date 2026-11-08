-- =====================================================================
-- Seguridad a nivel de fila
-- En Supabase, las tablas de public quedan expuestas por la API de datos.
-- Con RLS activo y sin políticas, la clave pública no puede leer ni escribir;
-- el rol del recolector es dueño de las tablas y no se ve afectado.
-- =====================================================================

ALTER TABLE cadena ENABLE ROW LEVEL SECURITY;
ALTER TABLE sucursal ENABLE ROW LEVEL SECURITY;
ALTER TABLE producto ENABLE ROW LEVEL SECURITY;
ALTER TABLE observacion_precio ENABLE ROW LEVEL SECURITY;
ALTER TABLE producto_canonico ENABLE ROW LEVEL SECURITY;
ALTER TABLE emparejamiento ENABLE ROW LEVEL SECURITY;
ALTER TABLE tipo_cambio ENABLE ROW LEVEL SECURITY;
ALTER TABLE ejecucion ENABLE ROW LEVEL SECURITY;
ALTER TABLE migracion_aplicada ENABLE ROW LEVEL SECURITY;
