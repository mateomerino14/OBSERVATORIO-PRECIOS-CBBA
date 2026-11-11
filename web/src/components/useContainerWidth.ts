// Ancho real del contenedor de un gráfico, para dibujar a escala 1:1.

import { useEffect, useRef, useState } from 'react';

export const DEFAULT_WIDTH = 760;
const MIN_WIDTH = 280;

/** Ancho en píxeles del contenedor, actualizado cuando cambia de tamaño. */
export function useContainerWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === 'undefined') {
      return undefined;
    }
    const observer = new ResizeObserver((entries) => {
      const measured = Math.round(entries[0].contentRect.width);
      if (measured > 0) {
        setWidth(Math.max(measured, MIN_WIDTH));
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}
