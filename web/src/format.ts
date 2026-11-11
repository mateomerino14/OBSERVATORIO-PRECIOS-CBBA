// Formato de números y fechas en español de Bolivia.

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const LONG_MONTHS = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

/** Número con coma decimal: 1234.5 -> "1.234,50". */
export function number(value: number, decimals = 2): string {
  return value.toLocaleString('es-BO', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Monto en bolivianos: "Bs 193,65". */
export function money(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return `Bs${NBSP}${number(value, decimals)}`;
}

/** Espacio que no se corta al final de una línea: "+22 %" nunca queda en dos renglones. */
const NBSP = '\u00a0';

/** Porcentaje con signo y signo menos tipográfico: "+22 %", "−45 %". */
export function percent(value: number, decimals = 0): string {
  const factor = 10 ** decimals;
  const rounded = Math.round(value * factor) / factor;
  const text = number(Math.abs(rounded), decimals);
  if (rounded > 0) {
    return `+${text}${NBSP}%`;
  }
  if (rounded < 0) {
    return `−${text}${NBSP}%`;
  }
  return `${text}${NBSP}%`;
}

/** Mes corto desde una fecha ISO: "2025-05-01" -> "may 25". */
export function shortMonth(iso: string): string {
  const [year, month] = iso.split('-');
  return `${MONTHS[Number(month) - 1]} ${year.slice(2)}`;
}

/** Fecha larga: "2026-11-11" -> "11 de noviembre de 2026". */
export function longDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split('-');
  return `${Number(day)} de ${LONG_MONTHS[Number(month) - 1]} de ${year}`;
}

/** Fecha corta: "2026-11-11" -> "11 nov 2026". */
export function shortDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split('-');
  return `${Number(day)} ${MONTHS[Number(month) - 1]} ${year}`;
}

/** Lista de meses (primer día, ISO) entre dos fechas, ambas incluidas. */
export function monthRange(from: string, to: string): string[] {
  const months: string[] = [];
  let [year, month] = from.split('-').map(Number);
  const [endYear, endMonth] = to.split('-').map(Number);
  while (year < endYear || (year === endYear && month <= endMonth)) {
    months.push(`${year}-${String(month).padStart(2, '0')}-01`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return months;
}

/** Primer día del mes de una fecha ISO. */
export function monthOf(iso: string): string {
  return `${iso.slice(0, 7)}-01`;
}
