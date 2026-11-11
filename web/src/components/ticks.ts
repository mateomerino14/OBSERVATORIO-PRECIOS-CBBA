// Ticks de ejes compartidos por los gráficos.

/** Ticks redondos que cubren un rango, con un paso dado. */
export function niceTicks(min: number, max: number, step: number): number[] {
  const ticks: number[] = [];
  for (let tick = Math.floor(min / step) * step; tick <= Math.ceil(max / step) * step; tick += step) {
    ticks.push(tick);
  }
  return ticks;
}
