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
  /** Modelo de similitud de texto; null si no hay productos con precio. */
  sugerencias: Suggestions | null;
  anomalias: Anomalies;
  /** K-means sobre los productos de mercado; null sin historia suficiente. */
  grupos_mercado: MarketGroups | null;
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

export type RejectionReason = 'nombre' | 'subcategoria' | 'presentacion' | 'aceptado';

export interface SuggestionRow {
  nombre: string;
  subcategoria: string | null;
  similitud: number;
  motivo: RejectionReason;
  url: string;
}

export interface Suggestions {
  productos_catalogo: number;
  evaluacion: { casos: number; encontrados: number; top: number; puesto_mediano: number | null };
  items: {
    codigo: string;
    nombre: string;
    aceptados: number;
    umbral: number;
    candidatos: SuggestionRow[];
    dudosos: SuggestionRow[];
  }[];
}

export interface Anomalies {
  mercado: {
    umbral_z: number;
    items: { codigo: string; nombre: string; mes: string; cambio_pct: number; cambio_comun_pct: number; z: number }[];
  };
  super: {
    fecha: string | null;
    dias: number;
    minimo_dias: number;
    cambio_minimo_pct: number;
    items: {
      nombre: string;
      sucursal: string;
      precio: number;
      mediana_previa: number;
      dias_previos: number;
      cambio_pct: number;
      oferta: boolean;
    }[];
  };
}

export interface MarketGroups {
  etapas: { inicio: string; pico: string; fin: string };
  k: number;
  siluetas: { k: number; silueta: number }[];
  grupos: {
    numero: number;
    nombre: string;
    volatilidad: number;
    subida_pct: number;
    bajada_pct: number;
    productos: string[];
  }[];
  productos: {
    codigo: string;
    nombre: string;
    grupo: number;
    volatilidad: number;
    subida_pct: number;
    bajada_pct: number;
  }[];
}
