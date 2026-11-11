// Forma del JSON que genera `observatorio exportar` (versión 1).

export interface DashboardData {
  version: number;
  generado_en: string;
  ciudad: string;
  ultimo_dia: string | null;
  ultima_corrida: LastRun | null;
  cobertura: Coverage;
  canasta: BasketSummary;
  canasta_mercado: MarketBasket;
  dolar: ExchangeRates;
  super_vs_mercado: SuperVsMarket;
  subidas_mercado: MarketRisers;
  productos: Product[];
}

export interface LastRun {
  iniciada_en: string;
  terminada_en: string | null;
  estado: 'completada' | 'con_errores' | 'fallida' | 'bloqueada';
  paginas_ok: number;
  paginas_error: number;
  precios: number;
}

export interface Coverage {
  sucursales: number;
  productos: number;
  dias: number;
  primer_dia: string | null;
}

export interface BasketDay {
  fecha: string;
  tipico: number;
  economico: number;
  items: number;
}

export interface BasketSummary {
  codigo: string;
  nombre: string;
  personas: number;
  periodo: string;
  items_total: number;
  hoy: BasketDay | null;
  ciudad_por_dia: BasketDay[];
  /** Costo sobre los ítems que todas las sucursales tienen ese día. */
  por_sucursal: (BasketDay & { sucursal: string; items_sucursal: number })[];
}

export interface MarketBasket {
  productos_comparables: string[];
  por_mes: { mes: string; total: number | null; comparable: number | null }[];
}

export interface MonthlyRate {
  mes: string;
  venta: number;
}

export interface ExchangeRates {
  oficial_hoy: { fecha: string; venta: number } | null;
  fin_tipo_fijo: { fecha: string; venta: number } | null;
  oficial_mensual: MonthlyRate[];
  paralelo_mensual: MonthlyRate[];
}

export interface SuperVsMarketRow {
  codigo: string;
  nombre: string;
  presentacion: string;
  mercado: number;
  super_tipico: number;
  super_minimo: number;
  diferencia_pct: number;
}

export interface SuperVsMarket {
  periodo_mercado: [string, string] | null;
  productos: SuperVsMarketRow[];
}

export interface MarketRisers {
  periodo: { desde: string[]; hasta: string[] } | null;
  productos: { codigo: string; nombre: string; variacion_pct: number }[];
}

export interface Product {
  codigo: string;
  nombre: string;
  categoria: string;
  cantidad_canasta: number;
  unidad: 'g' | 'ml' | 'u';
  unidad_visible: string;
  hoy: { tipico: number; minimo: number; productos: number } | null;
  mercado_mensual: { mes: string; precio: number }[];
  diario: { fecha: string; sucursal: string; tipico: number; minimo: number }[];
  tienda: {
    nombre: string;
    precio: number;
    precio_unidad: number;
    sucursales: number;
    url: string;
  }[];
}
