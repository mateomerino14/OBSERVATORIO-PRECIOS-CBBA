// Piezas de diseño compartidas: encabezado, tarjetas de indicador, figuras y barras.

import { useEffect, useRef, type ReactNode } from 'react';

export type Route = 'resumen' | 'super-vs-mercado' | 'productos' | 'fuentes';

const LINKS: { route: Route; label: string }[] = [
  { route: 'resumen', label: 'Resumen' },
  { route: 'super-vs-mercado', label: 'Súper vs. mercado' },
  { route: 'productos', label: 'Productos' },
  { route: 'fuentes', label: 'Fuentes y método' },
];

/** Valor de aria-current para un enlace: "page" solo en la pantalla actual. */
function currentFlag(route: Route, current: Route): 'page' | undefined {
  if (route === current) {
    return 'page';
  }
  return undefined;
}

/** Encabezado con el nombre del proyecto y la navegación entre pantallas. */
export function Header({ current }: { current: Route }) {
  const navRef = useRef<HTMLElement>(null);

  // En móvil la navegación se desliza: deja visible la pantalla actual.
  useEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>('[aria-current="page"]');
    active?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }, [current]);

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <a className="brand" href="#/resumen">
          <span className="brand-name">Observatorio de Precios</span>
          <span className="brand-city">COCHABAMBA</span>
        </a>
        <nav aria-label="Secciones" className="nav" ref={navRef}>
          {LINKS.map((link) => (
            <a
              key={link.route}
              href={`#/${link.route}`}
              className="nav-link"
              aria-current={currentFlag(link.route, current)}
            >
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}

/** Tarjeta con un número destacado. */
export function KpiCard(props: { label: string; value: string; unit?: string; note?: ReactNode; tone?: 'price' | 'dollar' | 'muted' }) {
  const showUnit = Boolean(props.unit) && props.value !== '—';
  return (
    <div className="card kpi">
      <span className="kpi-label">{props.label}</span>
      <span className={`kpi-value tone-${props.tone ?? 'ink'}`}>
        {props.value}
        {showUnit && <span className="kpi-unit"> /{props.unit}</span>}
      </span>
      {props.note && <span className="kpi-note">{props.note}</span>}
    </div>
  );
}

/** Contenedor de un gráfico o tabla con título, bajada y nota de fuente. */
export function Figure(props: { title: string; subtitle?: ReactNode; source?: ReactNode; legend?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <figure className={`card figure ${props.className ?? ''}`}>
      <figcaption className="figure-head">
        <span className="figure-titles">
          <span className="figure-title">{props.title}</span>
          {props.subtitle && <span className="figure-subtitle">{props.subtitle}</span>}
        </span>
        {props.legend}
      </figcaption>
      {props.children}
      {props.source && <p className="figure-source">{props.source}</p>}
    </figure>
  );
}

/** Leyenda de una serie: línea continua o punteada. */
export function LegendItem(props: { color: string; label: string; dashed?: boolean }) {
  let style: React.CSSProperties = { background: props.color };
  if (props.dashed) {
    style = { borderTop: `3px dashed ${props.color}`, height: 0 };
  }
  return (
    <span className="legend-item">
      <span className="legend-swatch" style={style} />
      {props.label}
    </span>
  );
}

/** Barra horizontal proporcional a un valor dentro de un máximo. */
export function Bar(props: { value: number; max: number; color: string; track?: string }) {
  const width = Math.max(0, Math.min(props.value / props.max, 1)) * 100;
  return (
    <span className="bar-track" style={{ background: props.track ?? '#EFECE5' }}>
      <span className="bar-fill" style={{ width: `${width.toFixed(1)}%`, background: props.color }} />
    </span>
  );
}

/** Barra divergente: naranja hacia la derecha si es positivo, azul hacia la izquierda si no. */
export function DivergingBar(props: { value: number; limit: number }) {
  const share = Math.min(Math.abs(props.value), props.limit) / props.limit;
  let positive = '0%';
  let negative = '0%';
  if (props.value >= 0) {
    positive = `${(share * 100).toFixed(1)}%`;
  } else {
    negative = `${(share * 100).toFixed(1)}%`;
  }
  return (
    <span className="diverging">
      <span className="diverging-neg">
        <span style={{ width: negative }} />
      </span>
      <span className="diverging-pos">
        <span style={{ width: positive }} />
      </span>
    </span>
  );
}

/** Aviso para una sección que todavía no tiene datos. */
export function EmptyState(props: { title: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-title">{props.title}</span>
      {props.children && <span className="empty-text">{props.children}</span>}
    </div>
  );
}
