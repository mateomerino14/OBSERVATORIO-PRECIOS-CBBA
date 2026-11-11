// Hallazgos en una frase, calculados desde los datos exportados para que se actualicen solos.

import { percent, shortMonth } from './format';
import type { DashboardData } from './types';

/** Meses mínimos con dólar y canasta para hablar de subida y bajada. */
const MIN_CYCLE_MONTHS = 3;

interface Finding {
  id: string;
  /** Cifra destacada, por ejemplo "+21 %". */
  value: string;
  title: string;
  text: string;
}

/** Cambio porcentual entre dos valores. */
function change(from: number, to: number): number {
  return (to / from - 1) * 100;
}

/** Subida (primer diciembre → pico) y bajada (pico → último mes) del paralelo frente a la canasta. */
export function dollarCycle(data: DashboardData) {
  const basket = new Map(
    data.canasta_mercado.por_mes
      .filter((row) => row.total !== null)
      .map((row) => [row.mes, row.total as number]),
  );
  const months = data.dolar.paralelo_mensual.filter((row) => basket.has(row.mes));
  if (months.length < MIN_CYCLE_MONTHS) {
    return null;
  }
  let peak = 0;
  months.forEach((row, index) => {
    if (row.venta > months[peak].venta) {
      peak = index;
    }
  });
  const last = months.length - 1;
  if (peak === 0 || peak === last) {
    return null;
  }
  const start = Math.max(months.findIndex((row) => row.mes.endsWith('-12-01')), 0);
  if (start >= peak) {
    return null;
  }
  const point = (index: number) => ({ mes: months[index].mes, dolar: months[index].venta, canasta: basket.get(months[index].mes) as number });
  const from = point(start);
  const top = point(peak);
  const end = point(last);
  return {
    subida: { desde: from, hasta: top, dolar: change(from.dolar, top.dolar), canasta: change(from.canasta, top.canasta) },
    bajada: { desde: top, hasta: end, dolar: change(top.dolar, end.dolar), canasta: change(top.canasta, end.canasta) },
  };
}

/** Hallazgos del Resumen; omite los que no tienen datos suficientes. */
export function buildFindings(data: DashboardData): Finding[] {
  const findings: Finding[] = [];

  const cycle = dollarCycle(data);
  if (cycle && cycle.bajada.dolar < 0) {
    const { subida, bajada } = cycle;
    findings.push({
      id: 'dolar',
      value: percent(bajada.canasta),
      title: 'Cuando el dólar bajó, los precios no',
      text:
        `De ${shortMonth(subida.desde.mes)} a ${shortMonth(subida.hasta.mes)} el dólar paralelo subió ${percent(subida.dolar)} y la canasta de mercado ${percent(subida.canasta)}. ` +
        `De ${shortMonth(bajada.desde.mes)} a ${shortMonth(bajada.hasta.mes)} el dólar bajó ${percent(-bajada.dolar).replace('+', '')}, pero la canasta siguió subiendo: ${percent(bajada.canasta)}.`,
    });
  }

  const rows = data.super_vs_mercado.productos;
  if (rows.length > 0) {
    const pricier = rows.filter((row) => row.diferencia_pct > 0).length;
    const sorted = [...rows].sort((left, right) => right.diferencia_pct - left.diferencia_pct);
    const top = sorted[0];
    const bottom = sorted.at(-1)!;
    let text = `${pricier} de ${rows.length} productos cuestan más en Hipermaxi que en los mercados (precio típico). El más caro en el súper: ${top.nombre.toLowerCase()}, ${percent(top.diferencia_pct)}.`;
    if (bottom.diferencia_pct < 0) {
      text += ` El más barato: ${bottom.nombre.toLowerCase()}, ${percent(bottom.diferencia_pct)}.`;
    }
    findings.push({
      id: 'super',
      value: `${pricier} de ${rows.length}`,
      title: 'El súper suele ser más caro, pero no en todo',
      text,
    });
  }

  const branches = data.canasta.por_sucursal.filter((row) => row.fecha === data.ultimo_dia);
  if (branches.length > 1) {
    const costs = branches.map((row) => row.tipico);
    const spread = change(Math.min(...costs), Math.max(...costs));
    findings.push({
      id: 'sucursales',
      value: percent(spread, 1).replace('+', ''),
      title: 'Todas las sucursales cobran casi lo mismo',
      text: `Sobre los ${branches[0].items} productos que tienen las ${branches.length} sucursales, la más cara cuesta ${percent(spread, 1).replace('+', '')} más que la más barata. Lo que cambia entre sucursales es qué productos publican en línea.`,
    });
  }

  return findings;
}
