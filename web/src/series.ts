// Series para los gráficos: índices, ticks de meses, huecos y precios diarios.

import { shortMonth } from './format';
import type { Product } from './types';

export const ALL_BRANCHES = 'Todas';
export const INDEX_BASE = 100;
// Ticks de meses: enero y julio, salvo cerca de los bordes (en meses).
const ANCHOR_MONTHS = ['01', '07'];
const EDGE_MARGIN = 3;

/** Índice base 100 en un mes dado; null donde falte el dato. */
export function toIndex(values: (number | null)[], baseIndex: number): (number | null)[] {
  const base = values[baseIndex];
  return values.map((value) => {
    if (value === null || base === null || base === undefined) {
      return null;
    }
    return (value / base) * INDEX_BASE;
  });
}

/** Ticks del eje X: el primer mes, cada enero y julio, y el último. */
export function monthTicks(months: string[]): { index: number; label: string }[] {
  const ticks: { index: number; label: string }[] = [];
  months.forEach((month, index) => {
    const isEdge = index === 0 || index === months.length - 1;
    const isAnchor = ANCHOR_MONTHS.includes(month.split('-')[1]);
    const nearEdge = index < EDGE_MARGIN || months.length - 1 - index < EDGE_MARGIN;
    if (isEdge || (isAnchor && !nearEdge)) {
      ticks.push({ index, label: shortMonth(month) });
    }
  });
  return ticks;
}

/** Tramo de meses consecutivos sin ningún dato, para sombrearlo en el gráfico. */
export function emptyStretch(values: (number | null)[]): { from: number; to: number } | null {
  let best: { from: number; to: number } | null = null;
  let start = -1;
  values.forEach((value, index) => {
    if (value === null && start < 0) {
      start = index;
    }
    const closes = value !== null || index === values.length - 1;
    if (start >= 0 && closes) {
      let end = index - 1;
      if (value === null) {
        end = index;
      }
      if (best === null || end - start > best.to - best.from) {
        best = { from: Math.max(start - 1, 0), to: Math.min(end + 1, values.length - 1) };
      }
      start = -1;
    }
  });
  return best;
}

/** Precio típico diario de un producto: de una sucursal o el promedio de todas. */
export function dailySeries(product: Product, branch: string): { days: string[]; values: number[] } {
  const byDay = new Map<string, number[]>();
  product.diario.forEach((row) => {
    if (branch !== ALL_BRANCHES && row.sucursal !== branch) {
      return;
    }
    const list = byDay.get(row.fecha) ?? [];
    list.push(row.tipico);
    byDay.set(row.fecha, list);
  });
  const days = [...byDay.keys()].sort();
  const values = days.map((day) => {
    const list = byDay.get(day) ?? [];
    return list.reduce((sum, value) => sum + value, 0) / list.length;
  });
  return { days, values };
}
