// Pantalla 1: indicadores, canasta en mercado y súper, subidas y dólar.

import { Bar, Figure, KpiCard, LegendItem } from '../components/Layout';
import { LineChart, type Marker } from '../components/LineChart';
import { longDate, money, monthOf, monthRange, number, percent, shortMonth } from '../format';
import { branchLabel } from './Productos';
import { buildFindings } from '../findings';
import type { DashboardData } from '../types';

const INK = '#1B1F24';
const PRICE = '#B4500B';
const DOLLAR = '#1F5FAD';
const TOP_RISERS = 6;

/** Ticks del eje X: el primer mes, cada enero y julio, y el último. */
export function monthTicks(months: string[]): { index: number; label: string }[] {
  const ticks: { index: number; label: string }[] = [];
  months.forEach((month, index) => {
    const isEdge = index === 0 || index === months.length - 1;
    const isAnchor = month.slice(5, 7) === '01' || month.slice(5, 7) === '07';
    const nearEnd = months.length - 1 - index < 3;
    if (isEdge || (isAnchor && !nearEnd && index > 2)) {
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

export function Resumen({ data }: { data: DashboardData }) {
  const today = data.canasta.hoy;
  const official = data.dolar.oficial_hoy;
  const fixed = data.dolar.fin_tipo_fijo;
  const risers = data.subidas_mercado.productos.slice(0, TOP_RISERS);
  const maxRise = Math.max(...risers.map((item) => item.variacion_pct), 1);

  const marketMonths = data.canasta_mercado.por_mes;
  const firstMonth = marketMonths[0]?.mes ?? data.dolar.oficial_mensual[0]?.mes;
  let lastMonth = data.dolar.oficial_mensual.at(-1)?.mes ?? firstMonth;
  if (data.ultimo_dia) {
    lastMonth = monthOf(data.ultimo_dia);
  }
  const months = monthRange(firstMonth, lastMonth);
  const marketValues = months.map((month) => marketMonths.find((row) => row.mes === month)?.comparable ?? null);

  const markers: Marker[] = [];
  if (today) {
    const index = months.indexOf(monthOf(today.fecha));
    markers.push({ index, value: today.tipico, color: PRICE, label: `Súper típico ${number(today.tipico)}` });
    markers.push({ index, value: today.economico, color: PRICE, hollow: true, label: `mínimo ${number(today.economico)}` });
  }
  const gap = emptyStretch(marketValues.map((value, index) => {
    if (markers.some((marker) => marker.index === index)) {
      return 0;
    }
    return value;
  }));
  const shaded = [];
  if (gap) {
    shaded.push({ ...gap, label: 'sin datos' });
  }

  const basketValues = [...marketValues.filter((value): value is number => value !== null), ...markers.map((marker) => marker.value)];
  const basketMax = Math.ceil(Math.max(...basketValues, 100) / 25) * 25;
  const basketMin = Math.floor(Math.min(...basketValues, basketMax) / 25) * 25;
  const basketTicks = [];
  for (let tick = basketMin; tick <= basketMax; tick += 25) {
    basketTicks.push(tick);
  }

  const officialValues = months.map((month) => data.dolar.oficial_mensual.find((row) => row.mes === month)?.venta ?? null);
  const parallelValues = months.map((month) => data.dolar.paralelo_mensual.find((row) => row.mes === month)?.venta ?? null);
  const verticalLines = [];
  if (fixed) {
    verticalLines.push({ index: months.indexOf(monthOf(fixed.fecha)), label: 'fin del tipo fijo' });
  }

  let officialChange = null;
  if (official && fixed) {
    officialChange = (official.venta / fixed.venta - 1) * 100;
  }
  let marketChange = null;
  const yearly = data.subidas_mercado.periodo;
  const totals = marketMonths.filter((row) => row.total !== null);
  if (yearly) {
    const average = (list: string[]) => {
      const values = list.map((month) => marketMonths.find((row) => row.mes === month)?.total).filter((value): value is number => typeof value === 'number');
      return values.reduce((sum, value) => sum + value, 0) / values.length;
    };
    marketChange = (average(yearly.hasta) / average(yearly.desde) - 1) * 100;
  }

  const latestBranches = data.canasta.por_sucursal
    .filter((row) => row.fecha === data.ultimo_dia)
    .sort((left, right) => left.tipico - right.tipico);
  const maxBranch = Math.max(...latestBranches.map((row) => row.tipico), 1);
  const commonItems = latestBranches[0]?.items ?? 0;

  const findings = buildFindings(data);

  let marketChangeText = '—';
  if (marketChange !== null) {
    marketChangeText = percent(marketChange);
  }

  return (
    <main className="page">
      <section className="intro">
        <p className="eyebrow">
          {data.ultimo_dia && `PRECIOS DEL ${longDate(data.ultimo_dia).toUpperCase()}`}
        </p>
        <h1>¿Cuánto cuesta comer en Cochabamba, y qué tiene que ver el dólar?</h1>
        <p className="lead">
          Precios diarios de las {data.cobertura.sucursales} sucursales de Hipermaxi, tipo de cambio del BCB y la historia de precios de mercado de la Defensoría del Pueblo desde {totals[0] && shortMonth(totals[0].mes)}.
        </p>
      </section>

      <section aria-label="Indicadores" className="kpis">
        <KpiCard
          label="Canasta en el súper (precio típico)"
          value={money(today?.tipico)}
          tone="price"
          note={today && `por semana · ${today.items} de ${data.canasta.items_total} productos con precio`}
        />
        <KpiCard label="Canasta comprando lo más barato" value={money(today?.economico)} note="misma canasta, otras marcas" />
        <KpiCard
          label="Dólar oficial BCB"
          value={money(official?.venta)}
          tone="dollar"
          note={officialChange !== null && fixed && `${percent(officialChange)} desde el fin del tipo fijo (${shortMonth(fixed.fecha)})`}
        />
        <KpiCard
          label="Canasta en mercados, último año"
          value={marketChangeText}
          note={yearly && `${shortMonth(yearly.desde[0])}–${shortMonth(yearly.desde.at(-1) ?? '')} → ${shortMonth(yearly.hasta[0])}–${shortMonth(yearly.hasta.at(-1) ?? '')} · Defensoría`}
        />
      </section>

      {findings.length > 0 && (
        <section aria-labelledby="hallazgos" className="findings">
          <h2 id="hallazgos" className="section-title">Lo que muestran los datos</h2>
          <ol>
            {findings.map((finding) => (
              <li key={finding.id} className="card finding">
                <span className="finding-value mono">{finding.value}</span>
                <h3>{finding.title}</h3>
                <p>{finding.text}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="row">
        <Figure
          className="grow"
          title="La misma canasta, en el mercado y en el súper"
          subtitle={`Bs por semana, los ${data.canasta_mercado.productos_comparables.length} productos que vende Hipermaxi`}
          source="Mercado: Defensoría del Pueblo, mensual. Súper: Hipermaxi, diario (promedio de sucursales)."
        >
          <LineChart
            categories={months}
            series={[{ id: 'mercado', color: INK, values: marketValues }]}
            yMin={basketMin}
            yMax={basketMax}
            yTicks={basketTicks}
            xTicks={monthTicks(months)}
            shaded={shaded}
            markers={markers}
            ariaLabel="Costo semanal de la canasta comparable en mercados de Cochabamba y en Hipermaxi"
          />
        </Figure>

        <Figure
          className="side"
          title="Mayores subidas en mercados"
          subtitle="Promedio de los últimos 3 meses frente a un año antes"
          source="Fuente: Defensoría del Pueblo."
        >
          <ol className="rank">
            {risers.map((item) => (
              <li key={item.codigo}>
                <span>{item.nombre}</span>
                <Bar value={item.variacion_pct} max={maxRise} color={PRICE} track="#F1E3D6" />
                <span className="mono">{percent(item.variacion_pct)}</span>
              </li>
            ))}
          </ol>
        </Figure>
      </section>

      {latestBranches.length > 1 && (
        <Figure
          title="La canasta en cada sucursal"
          subtitle={`Bs por semana, precio típico, sobre los ${commonItems} productos que tienen todas las sucursales`}
          source="Comparar solo productos comunes evita que una sucursal parezca más cara por vender más cosas."
        >
          <ol className="rank branches">
            {latestBranches.map((row) => (
              <li key={row.sucursal}>
                <span>{branchLabel(row.sucursal)}</span>
                <Bar value={row.tipico} max={maxBranch} color={PRICE} track="#F1E3D6" />
                <span className="mono">{money(row.tipico)}</span>
                <span className="muted small">
                  {row.items_sucursal} de {data.canasta.items_total} productos en línea
                </span>
              </li>
            ))}
          </ol>
        </Figure>
      )}

      <Figure
        title="Dos dólares: el oficial y el paralelo"
        subtitle="Bs por dólar, promedio mensual del oficial y cierre mensual del paralelo"
        legend={
          <span className="legend">
            <LegendItem color={DOLLAR} label="Oficial (BCB)" />
            <LegendItem color={INK} label="Paralelo (CEED)" dashed />
          </span>
        }
        source="Paralelo: aproximado, desde los boletines del CEED de CADECOCRUZ."
      >
        <LineChart
          categories={months}
          series={[
            { id: 'oficial', color: DOLLAR, width: 3, values: officialValues },
            { id: 'paralelo', color: INK, dashed: true, values: parallelValues },
          ]}
          yMin={6}
          yMax={18}
          yTicks={[6, 9, 12, 15, 18]}
          xTicks={monthTicks(months)}
          verticalLines={verticalLines}
          ariaLabel="Dólar oficial y paralelo por mes"
        />
      </Figure>
    </main>
  );
}
