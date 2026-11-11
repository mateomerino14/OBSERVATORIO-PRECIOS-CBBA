// Gráfico de líneas en SVG con huecos, zonas sombreadas y marcadores.
// El lienzo toma el ancho real del contenedor, así el texto mide lo mismo en cualquier tarjeta.

import { useEffect, useRef, useState } from 'react';

export interface Series {
  id: string;
  color: string;
  dashed?: boolean;
  width?: number;
  values: (number | null)[];
}

export interface Marker {
  index: number;
  value: number;
  color: string;
  label?: string;
  hollow?: boolean;
}

interface Props {
  categories: string[];
  series: Series[];
  yMin: number;
  yMax: number;
  yTicks: number[];
  xTicks: { index: number; label: string }[];
  ariaLabel: string;
  shaded?: { from: number; to: number; label: string }[];
  markers?: Marker[];
  verticalLines?: { index: number; label: string }[];
  formatTick?: (value: number) => string;
  height?: number;
}

const DEFAULT_WIDTH = 760;
// Separación mínima entre etiquetas del eje X, en píxeles.
const MIN_TICK_GAP = 64;
const MIN_WIDTH = 280;
const LEFT = 48;
const RIGHT = 16;
const TOP = 16;
const BOTTOM = 28;

/** Posición horizontal de una categoría. */
export function xPosition(index: number, count: number, width = DEFAULT_WIDTH): number {
  if (count <= 1) {
    return LEFT;
  }
  return LEFT + ((width - LEFT - RIGHT) * index) / (count - 1);
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

/** Ancho en píxeles del contenedor, actualizado cuando cambia de tamaño. */
function useContainerWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === 'undefined') {
      return undefined;
    }
    const observer = new ResizeObserver((entries) => {
      const measured = Math.round(entries[0].contentRect.width);
      if (measured > 0) {
        setWidth(Math.max(measured, MIN_WIDTH));
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/** Posición vertical de un valor dentro del rango del eje. */
export function yPosition(value: number, min: number, max: number, height: number): number {
  return TOP + (height - TOP - BOTTOM) * (1 - (value - min) / (max - min));
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

export function LineChart(props: Props) {
  const [container, width] = useContainerWidth();
  const height = props.height ?? 240;
  const count = props.categories.length;
  const x = (index: number) => xPosition(index, count, width);
  const y = (value: number) => yPosition(value, props.yMin, props.yMax, height);
  const format = props.formatTick ?? ((value: number) => String(value));

  return (
    <div ref={container} className="chart-box">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={props.ariaLabel} className="chart">
      <g className="chart-grid">
        {props.yTicks.map((tick) => (
          <line key={tick} x1={LEFT} x2={width - RIGHT} y1={y(tick)} y2={y(tick)} />
        ))}
      </g>
      <g className="chart-axis">
        {props.yTicks.map((tick) => (
          <text key={tick} x={LEFT - 8} y={y(tick) + 3} textAnchor="end">
            {format(tick)}
          </text>
        ))}
        {fitTicks(props.xTicks, x).map((tick, position) => {
          let anchor: 'start' | 'middle' | 'end' = 'middle';
          if (position === 0 && tick.index === 0) {
            anchor = 'start';
          } else if (tick.index === count - 1) {
            anchor = 'end';
          }
          return (
            <text key={tick.index} x={x(tick.index)} y={height - 6} textAnchor={anchor}>
              {tick.label}
            </text>
          );
        })}
      </g>
      {(props.shaded ?? []).map((zone) => (
        <g key={zone.from} className="chart-shade">
          <rect x={x(zone.from)} y={TOP} width={x(zone.to) - x(zone.from)} height={height - TOP - BOTTOM} />
          <text x={(x(zone.from) + x(zone.to)) / 2} y={(height - BOTTOM + TOP) / 2} textAnchor="middle">
            {zone.label}
          </text>
        </g>
      ))}
      {(props.verticalLines ?? []).map((line) => (
        <g key={line.index} className="chart-vline">
          <line x1={x(line.index)} x2={x(line.index)} y1={TOP} y2={height - BOTTOM} />
          <text x={x(line.index) - 6} y={TOP + 14} textAnchor="end">
            {line.label}
          </text>
        </g>
      ))}
      {props.series.map((serie) =>
        segments(serie.values).map((segment) => {
          if (segment.length === 1) {
            const point = segment[0];
            return (
              <circle key={`${serie.id}-${point.index}`} cx={x(point.index)} cy={y(point.value)} r={3.5} fill={serie.color} />
            );
          }
          const points = segment.map((point) => `${x(point.index).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ');
          let dash: string | undefined;
          if (serie.dashed) {
            dash = '6 4';
          }
          return (
            <polyline
              key={`${serie.id}-${segment[0].index}`}
              points={points}
              fill="none"
              stroke={serie.color}
              strokeWidth={serie.width ?? 2.5}
              strokeDasharray={dash}
              strokeLinejoin="round"
            />
          );
        }),
      )}
      {(props.markers ?? []).map((marker) => {
        const cx = x(marker.index);
        const cy = y(marker.value);
        let fill = marker.color;
        if (marker.hollow) {
          fill = '#FFFFFF';
        }
        let labelX = cx + 10;
        let anchor: 'start' | 'end' = 'start';
        if (cx > width * 0.7) {
          labelX = cx - 12;
          anchor = 'end';
        }
        return (
          <g key={`${marker.index}-${marker.value}`}>
            <circle cx={cx} cy={cy} r={6} fill={fill} stroke={marker.color} strokeWidth={2.5} />
            {marker.label && (
              <text x={labelX} y={cy + 4} textAnchor={anchor} className="chart-label" fill={marker.color}>
                {marker.label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
    </div>
  );
}
