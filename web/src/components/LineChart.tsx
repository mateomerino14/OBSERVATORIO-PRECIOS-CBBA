// Gráfico de líneas en SVG con huecos, zonas sombreadas y marcadores.
// El lienzo toma el ancho real del contenedor, así el texto mide lo mismo en cualquier tarjeta.

import { BOTTOM, fitTicks, LEFT, RIGHT, segments, TOP, xPosition, yPosition } from './lineGeometry';
import { useContainerWidth } from './useContainerWidth';

interface Series {
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

// Separaciones de texto en píxeles: del eje Y al número y de la base al centro de la letra.
const TICK_GAP = 8;
const TEXT_BASELINE = 3;
const LABEL_BASELINE = 4;
const X_TICK_FROM_BOTTOM = 6;
const VLINE_LABEL_GAP = 6;
const VLINE_LABEL_TOP = 14;
const POINT_RADIUS = 3.5;
const MARKER_RADIUS = 6;
const MARKER_LABEL_GAP = 10;
const MARKER_LABEL_GAP_LEFT = 12;
// Pasado este tramo del ancho, la etiqueta de un marcador va a la izquierda.
const MARKER_FLIP_SHARE = 0.7;
const LINE_WIDTH = 2.5;
const DASH = '6 4';
const HOLLOW_FILL = '#FFFFFF';

/** Gráfico de líneas en SVG que se ajusta al ancho de su contenedor. */
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
          <text key={tick} x={LEFT - TICK_GAP} y={y(tick) + TEXT_BASELINE} textAnchor="end">
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
            <text key={tick.index} x={x(tick.index)} y={height - X_TICK_FROM_BOTTOM} textAnchor={anchor}>
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
          <text x={x(line.index) - VLINE_LABEL_GAP} y={TOP + VLINE_LABEL_TOP} textAnchor="end">
            {line.label}
          </text>
        </g>
      ))}
      {props.series.map((serie) =>
        segments(serie.values).map((segment) => {
          if (segment.length === 1) {
            const point = segment[0];
            return (
              <circle key={`${serie.id}-${point.index}`} cx={x(point.index)} cy={y(point.value)} r={POINT_RADIUS} fill={serie.color} />
            );
          }
          const points = segment.map((point) => `${x(point.index).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ');
          let dash: string | undefined;
          if (serie.dashed) {
            dash = DASH;
          }
          return (
            <polyline
              key={`${serie.id}-${segment[0].index}`}
              points={points}
              fill="none"
              stroke={serie.color}
              strokeWidth={serie.width ?? LINE_WIDTH}
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
          fill = HOLLOW_FILL;
        }
        let labelX = cx + MARKER_LABEL_GAP;
        let anchor: 'start' | 'end' = 'start';
        if (cx > width * MARKER_FLIP_SHARE) {
          labelX = cx - MARKER_LABEL_GAP_LEFT;
          anchor = 'end';
        }
        return (
          <g key={`${marker.index}-${marker.value}`}>
            <circle cx={cx} cy={cy} r={MARKER_RADIUS} fill={fill} stroke={marker.color} strokeWidth={LINE_WIDTH} />
            {marker.label && (
              <text x={labelX} y={cy + LABEL_BASELINE} textAnchor={anchor} className="chart-label" fill={marker.color}>
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
