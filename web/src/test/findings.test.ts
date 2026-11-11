import { describe, expect, it } from 'vitest';
import { buildFindings, dollarCycle } from '../findings';
import type { DashboardData } from '../types';
import fixture from './dashboard.fixture.json';

const data = fixture as unknown as DashboardData;

describe('hallazgos', () => {
  it('encuentra el pico del dólar y compara subida y bajada', () => {
    const cycle = dollarCycle(data)!;
    expect(cycle.subida.hasta.mes).toBe('2025-05-01');
    expect(cycle.subida.desde.mes).toBe('2024-12-01');
    expect(cycle.bajada.hasta.mes).toBe('2025-12-01');
    expect(cycle.bajada.dolar).toBeCloseTo(-41.06, 1);
    expect(cycle.bajada.canasta).toBeCloseTo(20.59, 1);
  });

  it('sin pico interior no hay ciclo', () => {
    const flat = {
      ...data,
      dolar: { ...data.dolar, paralelo_mensual: data.dolar.paralelo_mensual.map((row, index) => ({ ...row, venta: index })) },
    };
    expect(dollarCycle(flat)).toBeNull();
    expect(buildFindings(flat).map((finding) => finding.id)).not.toContain('dolar');
  });

  it('arma los tres hallazgos con cifras del fixture', () => {
    const findings = buildFindings(data);
    expect(findings.map((finding) => finding.id)).toEqual(['dolar', 'super', 'sucursales']);
    expect(findings[0].value).toBe('+21\u00a0%');
    expect(findings[2].text).toContain('las 2 sucursales');
    expect(findings[0].text).toContain('el dólar bajó 41\u00a0%');
    expect(findings[0].text).toContain('subió +47\u00a0%');
  });
});
