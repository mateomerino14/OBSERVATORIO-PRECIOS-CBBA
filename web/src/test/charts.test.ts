import { describe, expect, it } from 'vitest';
import { routeFromHash } from '../routes';
import { fitTicks, segments, xPosition, yPosition } from '../components/lineGeometry';
import { branchLabel } from '../format';
import { dailySeries, emptyStretch, monthTicks, toIndex } from '../series';
import type { Product } from '../types';

describe('gráfico de líneas', () => {
  it('corta la línea en los huecos', () => {
    expect(segments([1, 2, null, 4])).toEqual([
      [{ index: 0, value: 1 }, { index: 1, value: 2 }],
      [{ index: 3, value: 4 }],
    ]);
  });

  it('ubica extremos en los bordes del área', () => {
    expect(xPosition(0, 10)).toBe(48);
    expect(xPosition(9, 10)).toBe(744);
    expect(yPosition(200, 100, 200, 240)).toBe(16);
    expect(yPosition(100, 100, 200, 240)).toBe(212);
  });
});

describe('cálculos de pantallas', () => {
  it('encuentra el tramo más largo sin datos', () => {
    expect(emptyStretch([1, 2, null, null, null, 6, null, 8])).toEqual({ from: 1, to: 5 });
    expect(emptyStretch([1, 2, 3])).toBeNull();
  });

  it('marca el primer mes, eneros, julios y el último', () => {
    const months = ['2024-08-01', '2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01', '2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01', '2025-05-01'];
    expect(monthTicks(months).map((tick) => tick.label)).toEqual(['ago 24', 'ene 25', 'may 25']);
  });

  it('omite un enero pegado al final para que no se encimen las etiquetas', () => {
    const months = ['2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01', '2025-01-01', '2025-02-01'];
    expect(monthTicks(months).map((tick) => tick.label)).toEqual(['sep 24', 'feb 25']);
  });

  it('lleva una serie a índice base 100', () => {
    expect(toIndex([50, 100, null, 150], 1)).toEqual([50, 100, null, 150]);
    expect(toIndex([null, 10], 0)).toEqual([null, null]);
  });

  it('resuelve la pantalla desde el hash', () => {
    expect(routeFromHash('#/productos')).toBe('productos');
    expect(routeFromHash('#/modelos')).toBe('modelos');
    expect(routeFromHash('#/no-existe')).toBe('resumen');
    expect(routeFromHash('')).toBe('resumen');
  });

  it('acorta los nombres de sucursal', () => {
    expect(branchLabel('HIPERMAXI JUAN DE LA ROSA')).toBe('Juan de la Rosa');
    expect(branchLabel('HIPERMAXI CIRCUNVALACION')).toBe('Circunvalación');
    expect(branchLabel('Todas')).toBe('Todas');
  });

  it('promedia el precio diario entre sucursales', () => {
    const product = {
      diario: [
        { fecha: '2026-11-11', sucursal: 'A', tipico: 10, minimo: 8 },
        { fecha: '2026-11-11', sucursal: 'B', tipico: 14, minimo: 9 },
        { fecha: '2026-11-12', sucursal: 'A', tipico: 11, minimo: 8 },
      ],
    } as Product;
    expect(dailySeries(product, 'Todas')).toEqual({ days: ['2026-11-11', '2026-11-12'], values: [12, 11] });
    expect(dailySeries(product, 'B')).toEqual({ days: ['2026-11-11'], values: [14] });
  });
});

describe('etiquetas del eje', () => {
  it('descarta las que se enciman y conserva la última', () => {
    const ticks = [{ index: 0 }, { index: 1 }, { index: 5 }, { index: 9 }, { index: 10 }];
    expect(fitTicks(ticks, (index) => index * 20).map((tick) => tick.index)).toEqual([0, 5, 10]);
  });
});
