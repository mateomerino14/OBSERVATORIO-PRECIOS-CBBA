-- =====================================================================
-- Quita la vista costo_canasta_diario
-- Sumaba por sucursal solo los ítems que cada una tenía ese día, así que una sucursal
-- con menos productos en línea parecía más barata. El costo de la ciudad y la
-- comparación entre sucursales sobre ítems comunes se calculan en la exportación
-- a partir de precio_canonico_diario.
-- =====================================================================

DROP VIEW IF EXISTS costo_canasta_diario;
