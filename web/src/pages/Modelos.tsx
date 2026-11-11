// Pantalla 4: modelos que señalan qué revisar (emparejamiento y precios anómalos).

import { EmptyState, Figure, KpiCard } from '../components/Layout';
import { money, number, percent, shortMonth } from '../format';
import type { DashboardData, RejectionReason, SuggestionRow } from '../types';
import { branchLabel } from './Productos';

export const REASONS: Record<RejectionReason, string> = {
  nombre: 'el nombre no coincide',
  subcategoria: 'otra subcategoría',
  presentacion: 'presentación fuera de rango',
  aceptado: 'aceptado, poco parecido al resto',
};

function SuggestionLine({ row, doubtful }: { row: SuggestionRow; doubtful?: boolean }) {
  let className = 'reason';
  if (doubtful) {
    className = 'reason doubt';
  }
  return (
    <li>
      <a href={row.url} target="_blank" rel="noreferrer">
        {row.nombre}
      </a>
      <span className={className}>{REASONS[row.motivo]}</span>
      <span className="mono score">{number(row.similitud)}</span>
    </li>
  );
}

export function Modelos({ data }: { data: DashboardData }) {
  const suggestions = data.sugerencias;
  const market = data.anomalias.mercado;
  const store = data.anomalias.super;
  const items = suggestions?.items.filter((item) => item.candidatos.length > 0 || item.dudosos.length > 0) ?? [];

  let catalogSize = '—';
  if (suggestions) {
    catalogSize = number(suggestions.productos_catalogo, 0);
  }
  let dayWord = 'días';
  if (store.dias === 1) {
    dayWord = 'día';
  }

  let foundShare = '—';
  let foundNote = 'todavía no hay productos aceptados';
  if (suggestions && suggestions.evaluacion.casos > 0) {
    const { encontrados, casos, top } = suggestions.evaluacion;
    foundShare = `${number((encontrados / casos) * 100, 0)} %`;
    foundNote = `${encontrados} de ${casos}: sin su regla, quedan entre las ${top} primeras sugerencias`;
  }

  return (
    <main className="page">
      <section className="intro">
        <h1>Dos modelos para saber qué revisar</h1>
        <p className="lead">
          No cambian ningún precio. El primero busca productos que las reglas de la canasta podrían estar dejando fuera; el segundo, saltos de precio que no siguen al resto del mercado.
        </p>
      </section>

      <section aria-label="Indicadores de los modelos" className="kpis">
        <KpiCard label="Aceptados que el modelo reencuentra" value={foundShare} tone="price" note={foundNote} />
        <KpiCard
          label="Catálogo comparado"
          value={catalogSize}
          note="productos de Hipermaxi con precio el último día"
        />
        <KpiCard
          label="Saltos anómalos en mercados"
          value={number(market.items.length, 0)}
          note={`z-score modificado de ${number(market.umbral_z, 1)} o más · Defensoría`}
        />
      </section>

      <Figure
        title="¿Qué se les escapa a las reglas de la canasta?"
        subtitle="Productos parecidos a los que cada ítem ya acepta, por similitud de texto (TF-IDF de n-gramas de caracteres). La cifra es la similitud, de 0 a 1."
        source="Cada ítem tiene su propio umbral: el percentil 10 de la similitud de sus productos aceptados. Las sugerencias se revisan a mano; así se sumaron los packs de huevos y se sacaron las pastas sin gluten."
      >
        {items.length === 0 && <EmptyState title="Sin sugerencias por ahora" />}
        {items.length > 0 && (
          <div className="suggestions">
            {items.map((item) => (
              <section key={item.codigo} className="suggestion-item">
                <h3>
                  {item.nombre}
                  <span className="muted small">
                    {' '}
                    · {item.aceptados} aceptados · umbral {number(item.umbral)}
                  </span>
                </h3>
                <ul>
                  {item.candidatos.map((row) => (
                    <SuggestionLine key={row.url} row={row} />
                  ))}
                  {item.dudosos.map((row) => (
                    <SuggestionLine key={row.url} row={row} doubtful />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </Figure>

      <Figure
        title="Saltos de precio en los mercados"
        subtitle="Meses en que un producto se movió muy distinto al resto de la canasta y a su propia historia"
        source="Se resta el cambio mediano de todos los productos ese mes, así la inflación y el dólar no cuentan como anomalía. Una baja seguida de una subida parecida suele ser un error del sondeo."
      >
        {market.items.length === 0 && <EmptyState title="Ningún salto fuera de lo normal" />}
        {market.items.length > 0 && (
          <div className="table-scroll">
            <table className="table stack">
              <thead>
                <tr>
                  <th scope="col">Producto</th>
                  <th scope="col">Mes</th>
                  <th scope="col" className="num">Cambio del producto</th>
                  <th scope="col" className="num">Resto de la canasta</th>
                  <th scope="col" className="num">z</th>
                </tr>
              </thead>
              <tbody>
                {market.items.map((row) => (
                  <tr key={`${row.codigo}-${row.mes}`}>
                    <th scope="row">{row.nombre}</th>
                    <td data-label="Mes">{shortMonth(row.mes)}</td>
                    <td className="num mono tone-price" data-label="Cambio del producto">
                      {percent(row.cambio_pct)}
                    </td>
                    <td className="num mono" data-label="Resto de la canasta">
                      {percent(row.cambio_comun_pct)}
                    </td>
                    <td className="num mono" data-label="z">
                      {number(row.z, 1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Figure>

      <Figure
        title="Saltos de precio en el súper"
        subtitle={`Productos de la canasta cuyo precio cambió ${number(store.cambio_minimo_pct, 0)} % o más frente a su mediana de los días anteriores, en la misma sucursal`}
      >
        {store.dias < store.minimo_dias && (
          <EmptyState title={`Se activa con ${store.minimo_dias} días de precios`}>
            Hay {store.dias} {dayWord}. La recolección diaria lo completa sola.
          </EmptyState>
        )}
        {store.dias >= store.minimo_dias && store.items.length === 0 && (
          <EmptyState title="Ningún salto el último día" />
        )}
        {store.items.length > 0 && (
          <div className="table-scroll">
            <table className="table stack">
              <thead>
                <tr>
                  <th scope="col">Producto</th>
                  <th scope="col">Sucursal</th>
                  <th scope="col" className="num">Precio</th>
                  <th scope="col" className="num">Mediana previa</th>
                  <th scope="col" className="num">Cambio</th>
                </tr>
              </thead>
              <tbody>
                {store.items.map((row) => (
                  <tr key={`${row.nombre}-${row.sucursal}`}>
                    <th scope="row" className="plain">
                      {row.nombre}
                      {row.oferta && <span className="reason">en oferta</span>}
                    </th>
                    <td data-label="Sucursal">{branchLabel(row.sucursal)}</td>
                    <td className="num mono" data-label="Precio">
                      {money(row.precio)}
                    </td>
                    <td className="num mono" data-label="Mediana previa">
                      {money(row.mediana_previa)}
                    </td>
                    <td className="num mono tone-price" data-label="Cambio">
                      {percent(row.cambio_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Figure>
    </main>
  );
}
