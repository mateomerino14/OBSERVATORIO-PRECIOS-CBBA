// Gráfico de dispersión en SVG con líneas en cero y etiquetas que no se enciman.

import { placeLabels, RADIUS, TEXT_BASELINE, tickEvery } from './scatterLayout';
import { useContainerWidth } from './useContainerWidth';

interface ScatterPoint {
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
// Separaciones de texto en píxeles: del eje al número.
const TICK_GAP = 8;
const X_TICK_OFFSET = 16;
const X_TITLE_FROM_BOTTOM = 6;
const Y_TITLE_X = 14;
const DEFAULT_HEIGHT = 360;

/** Gráfico de dispersión en SVG que se ajusta al ancho de su contenedor. */
export function ScatterChart(props: Props) {
  const [container, width] = useContainerWidth();
  const height = props.height ?? DEFAULT_HEIGHT;
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
            <text key={tick} x={LEFT - TICK_GAP} y={y(tick) + TEXT_BASELINE} textAnchor="end">
              {format(tick)}
            </text>
          ))}
          {props.xTicks
            .filter((_, index) => (index - zeroTick) % every === 0)
            .map((tick) => (
              <text key={tick} x={x(tick)} y={height - BOTTOM + X_TICK_OFFSET} textAnchor="middle">
                {format(tick)}
              </text>
            ))}
          <text x={(LEFT + width - RIGHT) / 2} y={height - X_TITLE_FROM_BOTTOM} textAnchor="middle" className="chart-title">
            {props.xTitle}
          </text>
          <text x={Y_TITLE_X} y={(TOP + height - BOTTOM) / 2} textAnchor="middle" className="chart-title" transform={`rotate(-90 ${Y_TITLE_X} ${(TOP + height - BOTTOM) / 2})`}>
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
