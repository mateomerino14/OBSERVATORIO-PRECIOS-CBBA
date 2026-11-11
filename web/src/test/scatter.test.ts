import { describe, expect, it } from 'vitest';
import { placeLabels, tickEvery } from '../components/scatterLayout';
import { niceTicks } from '../components/ticks';

const AREA = { left: 0, right: 400, top: 0, bottom: 300 };

describe('gráfico de dispersión', () => {
  it('niceTicks cubre el rango con pasos redondos', () => {
    expect(niceTicks(-29, 121, 25)).toEqual([-50, -25, 0, 25, 50, 75, 100, 125]);
    expect(niceTicks(0, 20, 25)).toEqual([0, 25]);
  });

  it('tickEvery salta etiquetas del eje cuando no hay lugar', () => {
    expect(tickEvery(9, 1100)).toBe(1);
    expect(tickEvery(9, 300)).toBe(2);
    expect(tickEvery(1, 300)).toBe(1);
  });

  it('pone la etiqueta a la derecha si hay lugar', () => {
    const [label] = placeLabels([{ cx: 100, cy: 100, label: 'Arroz' }], AREA);
    expect(label).toEqual({ x: 107, y: 104, anchor: 'start' });
  });

  it('busca otro lado cuando la derecha está ocupada o fuera del área', () => {
    const labels = placeLabels(
      [
        { cx: 100, cy: 100, label: 'Arroz' },
        { cx: 100, cy: 108, label: 'Azúcar' },
        { cx: 395, cy: 150, label: 'Tomate' },
      ],
      AREA,
    );
    expect(labels[0]?.anchor).toBe('start');
    // A la derecha pisaría la etiqueta de Arroz: va a la izquierda.
    expect(labels[1]?.anchor).toBe('end');
    expect(labels[2]?.anchor).toBe('end');
  });

  it('omite la etiqueta si no cabe en ningún lado', () => {
    const [label] = placeLabels([{ cx: 5, cy: 5, label: 'Un nombre muy largo que no cabe' }], {
      left: 0,
      right: 20,
      top: 0,
      bottom: 20,
    });
    expect(label).toBeNull();
  });
});
