// Gráfico de dispersión en SVG con líneas en cero y etiquetas que no se enciman.

import { useContainerWidth } from './LineChart';

export interface ScatterPoint {
  id: string;
  label: string;
  x: number;
  y: number;
  color: string;
}

interface Props {
  points: ScatterPoint[];
  xTicks: number[];
  yTicks: number[];
  xTitle: string;
  yTitle: string;
  ariaLabel: string;
  formatTick?: (value: number) => string;
  height?: number;
}

const LEFT = 56;
const RIGHT = 16;
const TOP = 16;
const BOTTOM = 44;
const RADIUS = 5;
const LABEL_HEIGHT = 14;
// Ancho aproximado de un carácter de 12 px, para estimar el largo de una etiqueta.
const CHAR_WIDTH = 6.6;
const LABEL_GAP = 7;
// Separación mínima entre etiquetas del eje X, en píxeles.
const MIN_TICK_GAP = 48;

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Ticks redondos que cubren un rango, con un paso dado. */
export function niceTicks(min: number, max: number, step: number): number[] {
  const ticks: number[] = [];
  for (let tick = Math.floor(min / step) * step; tick <= Math.ceil(max / step) * step; tick += step) {
    ticks.push(tick);
  }
  return ticks;
}

/** Cada cuántos ticks se escribe la etiqueta para que no se enciman (1 = todos). */
export function tickEvery(count: number, span: number): number {
  if (count < 2) {
    return 1;
  }
  return Math.max(1, Math.ceil(MIN_TICK_GAP / (span / (count - 1))));
}

function overlaps(a: Box, b: Box): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/**
 * Lugar para cada etiqueta: a la derecha, a la izquierda, arriba o abajo del punto, el primero
 * que no pise otra etiqueta, otro punto ni el borde. Null si no cabe en ninguno.
 */
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
      { x: point.cx + LABEL_GAP, y: point.cy + 4, anchor: 'start' as const, left: point.cx + LABEL_GAP },
      { x: point.cx - LABEL_GAP, y: point.cy + 4, anchor: 'end' as const, left: point.cx - LABEL_GAP - width },
      { x: point.cx, y: point.cy - LABEL_GAP - 2, anchor: 'middle' as const, left: point.cx - width / 2 },
      { x: point.cx, y: point.cy + LABEL_GAP + LABEL_HEIGHT - 2, anchor: 'middle' as const, left: point.cx - width / 2 },
    ];
    for (const option of options) {
      const box = { left: option.left, right: option.left + width, top: option.y - LABEL_HEIGHT + 3, bottom: option.y + 3 };
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

export function ScatterChart(props: Props) {
  const [container, width] = useContainerWidth();
  const height = props.height ?? 360;
  const format = props.formatTick ?? ((value: number) => String(value));
  const xMin = props.xTicks[0];
  const xMax = props.xTicks[props.xTicks.length - 1];
  const yMin = props.yTicks[0];
  const yMax = props.yTicks[props.yTicks.length - 1];
  const x = (value: number) => LEFT + ((width - LEFT - RIGHT) * (value - xMin)) / (xMax - xMin);
  const y = (value: number) => TOP + ((height - TOP - BOTTOM) * (yMax - value)) / (yMax - yMin);
  const placed = props.points.map((point) => ({ cx: x(point.x), cy: y(point.y), label: point.label }));
  const labels = placeLabels(placed, { left: LEFT, right: width - RIGHT, top: TOP, bottom: height - BOTTOM });
  const every = tickEvery(props.xTicks.length, width - LEFT - RIGHT);
  // Al saltar etiquetas se conserva la del cero, la referencia del gráfico.
  const zeroTick = Math.max(props.xTicks.indexOf(0), 0);

  return (
    <div ref={container} className="chart-box">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={props.ariaLabel} className="chart">
        <g className="chart-grid">
          {props.yTicks.map((tick) => (
            <line key={`y${tick}`} x1={LEFT} x2={width - RIGHT} y1={y(tick)} y2={y(tick)} />
          ))}
          {props.xTicks.map((tick) => (
            <line key={`x${tick}`} x1={x(tick)} x2={x(tick)} y1={TOP} y2={height - BOTTOM} />
          ))}
        </g>
        <g className="chart-zero">
          {xMin < 0 && xMax > 0 && <line x1={x(0)} x2={x(0)} y1={TOP} y2={height - BOTTOM} />}
          {yMin < 0 && yMax > 0 && <line x1={LEFT} x2={width - RIGHT} y1={y(0)} y2={y(0)} />}
        </g>
        <g className="chart-axis">
          {props.yTicks.map((tick) => (
            <text key={tick} x={LEFT - 8} y={y(tick) + 3} textAnchor="end">
              {format(tick)}
            </text>
          ))}
          {props.xTicks
            .filter((_, index) => (index - zeroTick) % every === 0)
            .map((tick) => (
              <text key={tick} x={x(tick)} y={height - BOTTOM + 16} textAnchor="middle">
                {format(tick)}
              </text>
            ))}
          <text x={(LEFT + width - RIGHT) / 2} y={height - 6} textAnchor="middle" className="chart-title">
            {props.xTitle}
          </text>
          <text x={14} y={(TOP + height - BOTTOM) / 2} textAnchor="middle" className="chart-title" transform={`rotate(-90 14 ${(TOP + height - BOTTOM) / 2})`}>
            {props.yTitle}
          </text>
        </g>
        {props.points.map((point, index) => (
          <g key={point.id}>
            <circle cx={placed[index].cx} cy={placed[index].cy} r={RADIUS} fill={point.color}>
              <title>{point.label}</title>
            </circle>
          </g>
        ))}
        {props.points.map((point, index) => {
          const label = labels[index];
          if (!label) {
            return null;
          }
          return (
            <text key={`l${point.id}`} x={label.x} y={label.y} textAnchor={label.anchor} className="chart-label" fill={point.color}>
              {point.label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
