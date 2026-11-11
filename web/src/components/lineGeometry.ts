// Geometría del gráfico de líneas: márgenes, posiciones, tramos y etiquetas del eje X.

import { DEFAULT_WIDTH } from './useContainerWidth';

export const LEFT = 48;
export const RIGHT = 16;
export const TOP = 16;
export const BOTTOM = 28;
// Separación mínima entre etiquetas del eje X, en píxeles.
const MIN_TICK_GAP = 64;

/** Posición horizontal de una categoría. */
export function xPosition(index: number, count: number, width = DEFAULT_WIDTH): number {
  if (count <= 1) {
    return LEFT;
  }
  return LEFT + ((width - LEFT - RIGHT) * index) / (count - 1);
}

/** Posición vertical de un valor dentro del rango del eje. */
export function yPosition(value: number, min: number, max: number, height: number): number {
  return TOP + (height - TOP - BOTTOM) * (1 - (value - min) / (max - min));
}

/** Etiquetas del eje X que caben sin encimarse; la última siempre se conserva. */
export function fitTicks<T extends { index: number }>(ticks: T[], position: (index: number) => number): T[] {
  const kept: T[] = [];
  const last = ticks[ticks.length - 1];
  ticks.forEach((tick) => {
    const previous = kept[kept.length - 1];
    if (previous && position(tick.index) - position(previous.index) < MIN_TICK_GAP) {
      if (tick === last) {
        kept.pop();
        kept.push(tick);
      }
      return;
    }
    kept.push(tick);
  });
  return kept;
}

/** Tramos continuos de una serie: cada hueco (null) corta la línea. */
export function segments(values: (number | null)[]): { index: number; value: number }[][] {
  const result: { index: number; value: number }[][] = [];
  let current: { index: number; value: number }[] = [];
  values.forEach((value, index) => {
    if (value === null) {
      if (current.length > 0) {
        result.push(current);
      }
      current = [];
      return;
    }
    current.push({ index, value });
  });
  if (current.length > 0) {
    result.push(current);
  }
  return result;
}
