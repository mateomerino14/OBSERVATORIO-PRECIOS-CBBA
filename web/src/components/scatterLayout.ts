// Ubicación de etiquetas del gráfico de dispersión, sin que se enciman entre sí ni con los puntos.

export const RADIUS = 5;
// De la base al centro de la letra, en píxeles.
export const TEXT_BASELINE = 3;
const LABEL_HEIGHT = 14;
// Ancho aproximado de un carácter de 12 px, para estimar el largo de una etiqueta.
const CHAR_WIDTH = 6.6;
const LABEL_GAP = 7;
const LABEL_BASELINE = 4;
// Ajuste de las etiquetas puestas arriba o abajo del punto.
const VERTICAL_NUDGE = 2;
// Separación mínima entre etiquetas del eje X, en píxeles.
const MIN_TICK_GAP = 48;

interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Si dos rectángulos se pisan. */
function overlaps(a: Box, b: Box): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/** Cada cuántos ticks se escribe la etiqueta para que no se enciman (1 = todos). */
export function tickEvery(count: number, span: number): number {
  if (count < 2) {
    return 1;
  }
  return Math.max(1, Math.ceil(MIN_TICK_GAP / (span / (count - 1))));
}

/** Lugar de cada etiqueta: derecha, izquierda, arriba o abajo, el primero libre; null si no cabe. */
export function placeLabels(
  points: { cx: number; cy: number; label: string }[],
  area: Box,
): ({ x: number; y: number; anchor: 'start' | 'end' | 'middle' } | null)[] {
  const taken: Box[] = points.map((point) => ({
    left: point.cx - RADIUS,
    right: point.cx + RADIUS,
    top: point.cy - RADIUS,
    bottom: point.cy + RADIUS,
  }));
  return points.map((point, own) => {
    const width = point.label.length * CHAR_WIDTH;
    const options = [
      { x: point.cx + LABEL_GAP, y: point.cy + LABEL_BASELINE, anchor: 'start' as const, left: point.cx + LABEL_GAP },
      { x: point.cx - LABEL_GAP, y: point.cy + LABEL_BASELINE, anchor: 'end' as const, left: point.cx - LABEL_GAP - width },
      { x: point.cx, y: point.cy - LABEL_GAP - VERTICAL_NUDGE, anchor: 'middle' as const, left: point.cx - width / 2 },
      { x: point.cx, y: point.cy + LABEL_GAP + LABEL_HEIGHT - VERTICAL_NUDGE, anchor: 'middle' as const, left: point.cx - width / 2 },
    ];
    for (const option of options) {
      const box = { left: option.left, right: option.left + width, top: option.y - LABEL_HEIGHT + TEXT_BASELINE, bottom: option.y + TEXT_BASELINE };
      const inside = box.left >= area.left && box.right <= area.right && box.top >= area.top && box.bottom <= area.bottom;
      const free = taken.every((other, index) => index === own || !overlaps(box, other));
      if (inside && free) {
        taken.push(box);
        return { x: option.x, y: option.y, anchor: option.anchor };
      }
    }
    return null;
  });
}
