// Pantalla 2: súper frente a mercado, producto por producto, y precios frente al dólar.

import { DivergingBar, EmptyState, Figure, LegendItem } from '../components/Layout';
import { LineChart } from '../components/LineChart';
import { money, monthOf, number, percent, shortMonth } from '../format';
import type { DashboardData } from '../types';

const INK = '#1B1F24';
const PRICE = '#B4500B';
const DIFF_LIMIT = 50;
const INDEX_BASE = 100;

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

export function SuperVsMercado({ data }: { data: DashboardData }) {
  const rows = data.super_vs_mercado.productos;
  const period = data.super_vs_mercado.periodo_mercado;

  // Meses con canasta completa de mercado y paralelo a la vez.
  const parallel = new Map(data.dolar.paralelo_mensual.map((row) => [monthOf(row.mes), row.venta]));
  const months = data.canasta_mercado.por_mes.filter((row) => row.total !== null && parallel.has(row.mes)).map((row) => row.mes);
  const decemberIndex = months.findIndex((month) => month.endsWith('-12-01'));
  const baseIndex = Math.max(decemberIndex, 0);
  const basket = toIndex(months.map((month) => data.canasta_mercado.por_mes.find((row) => row.mes === month)?.total ?? null), baseIndex);
  const dollar = toIndex(months.map((month) => parallel.get(month) ?? null), baseIndex);
  const values = [...basket, ...dollar].filter((value): value is number => value !== null);
  const yMin = Math.floor(Math.min(...values, INDEX_BASE) / 20) * 20;
  const yMax = Math.ceil(Math.max(...values, INDEX_BASE) / 20) * 20;
  const ticks = [];
  for (let tick = yMin; tick <= yMax; tick += 20) {
    ticks.push(tick);
  }
  const peak = dollar.reduce<number>((best, value, index) => {
    if (value !== null && (dollar[best] ?? -Infinity) < value) {
      return index;
    }
    return best;
  }, 0);
  const change = (series: (number | null)[], from: number, to: number) => {
    const start = series[from];
    const end = series[to];
    if (start === null || end === null || start === undefined || end === undefined) {
      return null;
    }
    return (end / start - 1) * 100;
  };
  const last = months.length - 1;

  let subtitle = 'Hipermaxi, último día';
  if (period && data.ultimo_dia) {
    subtitle = `Hipermaxi, ${shortMonth(data.ultimo_dia)} · Mercado: Defensoría, promedio ${shortMonth(period[0])} – ${shortMonth(period[1])}`;
  }

  return (
    <main className="page">
      <section className="intro">
        <h1>¿Es más caro el supermercado que el mercado?</h1>
        <p className="lead">
          Precio típico de Hipermaxi frente al promedio de mercado de los últimos meses con datos, en la misma presentación que usa la Defensoría. Si entre las dos fechas pasó tiempo, la diferencia real hoy es probablemente menor.
        </p>
      </section>

      <Figure
        title="Diferencia del precio típico del súper contra el mercado"
        subtitle={subtitle}
        source="Naranja: el súper cuesta más. Azul: cuesta menos. Los frescos no aparecen porque Hipermaxi casi no los vende en línea."
      >
        {rows.length === 0 && <EmptyState title="Todavía no hay productos comparables" />}
        {rows.length > 0 && (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Producto</th>
                  <th scope="col">Presentación</th>
                  <th scope="col" className="num">Mercado</th>
                  <th scope="col" className="num">Súper típico</th>
                  <th scope="col" className="num">Súper mínimo</th>
                  <th scope="col" className="diff-col">Súper típico vs. mercado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.codigo}>
                    <th scope="row">{row.nombre}</th>
                    <td className="muted">{row.presentacion}</td>
                    <td className="num mono">{money(row.mercado)}</td>
                    <td className="num mono tone-price">{money(row.super_tipico)}</td>
                    <td className="num mono">{money(row.super_minimo)}</td>
                    <td>
                      <span className="diff-cell">
                        <DivergingBar value={row.diferencia_pct} limit={DIFF_LIMIT} />
                        <span className="mono">{percent(row.diferencia_pct)}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Figure>

      {months.length > 1 && (
        <Figure
          title="Los precios subieron con el dólar, pero no bajaron con él"
          subtitle={`Índice, ${shortMonth(months[baseIndex])} = 100. Canasta completa en mercados de Cochabamba.`}
          legend={
            <span className="legend">
              <LegendItem color={PRICE} label="Canasta" />
              <LegendItem color={INK} label="Dólar paralelo" dashed />
            </span>
          }
          source="Canasta: Defensoría del Pueblo. Paralelo: aproximado, CEED de CADECOCRUZ."
        >
          <LineChart
            categories={months}
            series={[
              { id: 'canasta', color: PRICE, width: 3, values: basket },
              { id: 'paralelo', color: INK, dashed: true, values: dollar },
            ]}
            yMin={yMin}
            yMax={yMax}
            yTicks={ticks}
            xTicks={[
              { index: 0, label: shortMonth(months[0]) },
              { index: peak, label: shortMonth(months[peak]) },
              { index: last, label: shortMonth(months[last]) },
            ]}
            height={260}
            ariaLabel="Índice de la canasta de mercado frente al dólar paralelo"
          />
          <div className="facts">
            <Fact label={`${shortMonth(months[baseIndex])} → ${shortMonth(months[peak])}`} dollar={change(dollar, baseIndex, peak)} basket={change(basket, baseIndex, peak)} />
            <Fact label={`${shortMonth(months[peak])} → ${shortMonth(months[last])}`} dollar={change(dollar, peak, last)} basket={change(basket, peak, last)} />
          </div>
        </Figure>
      )}
    </main>
  );
}

/** Dato resumido de un tramo: cuánto cambió el dólar y cuánto la canasta. */
function Fact(props: { label: string; dollar: number | null; basket: number | null }) {
  if (props.dollar === null || props.basket === null) {
    return null;
  }
  return (
    <div className="fact">
      <span className="muted">{props.label}</span>
      <span>
        Paralelo <strong className="mono">{percent(props.dollar)}</strong> · canasta{' '}
        <strong className="mono">{percent(props.basket)}</strong>
      </span>
      <span className="muted small">{number(Math.abs(props.basket - props.dollar), 0)} puntos de diferencia</span>
    </div>
  );
}
