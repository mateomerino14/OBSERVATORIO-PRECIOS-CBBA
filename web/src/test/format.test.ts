import { describe, expect, it } from 'vitest';
import { longDate, money, monthOf, monthRange, number, percent, shortDate, shortMonth } from '../format';

describe('formato', () => {
  it('usa coma decimal y punto de miles', () => {
    expect(number(1234.5)).toBe('1.234,50');
    expect(money(193.65)).toBe('Bs\u00a0193,65');
    expect(money(null)).toBe('—');
  });

  it('escribe porcentajes con signo tipográfico', () => {
    expect(percent(22.4)).toBe('+22\u00a0%');
    expect(percent(-45.1)).toBe('−45\u00a0%');
    expect(percent(0)).toBe('0\u00a0%');
  });

  it('nombra meses y fechas en español', () => {
    expect(shortMonth('2025-05-01')).toBe('may 25');
    expect(shortDate('2026-11-11')).toBe('11 nov 2026');
    expect(longDate('2026-11-11T07:17:00Z')).toBe('11 de noviembre de 2026');
    expect(monthOf('2026-11-11')).toBe('2026-11-01');
  });

  it('arma rangos de meses que cruzan el año', () => {
    expect(monthRange('2024-11-01', '2025-02-01')).toEqual(['2024-11-01', '2024-12-01', '2025-01-01', '2025-02-01']);
  });
});

describe('porcentajes que redondean a cero', () => {
  it('no muestran signo', () => {
    expect(percent(-0.2)).toBe('0\u00a0%');
    expect(percent(0.4)).toBe('0\u00a0%');
  });
});
