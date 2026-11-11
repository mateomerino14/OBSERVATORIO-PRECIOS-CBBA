// Pantalla 4: estado de la recolección, fuentes, método y límites.

import { shortDate } from '../format';
import type { DashboardData, LastRun } from '../types';

const REPOSITORY = 'https://github.com/mateomerino14/OBSERVATORIO-PRECIOS-CBBA';
const STATUS: Record<LastRun['estado'], { label: string; color: string }> = {
  completada: { label: 'Completada', color: '#1F7A4D' },
  con_errores: { label: 'Completada con errores', color: '#B4500B' },
  fallida: { label: 'Fallida', color: '#B42318' },
  bloqueada: { label: 'Bloqueada por la tienda', color: '#B42318' },
};

/** Hora local de Bolivia de una marca de tiempo ISO. */
function boliviaTime(iso: string): string {
  return new Date(iso).toLocaleString('es-BO', {
    timeZone: 'America/La_Paz',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Pantalla de fuentes, cobertura, método y límites. */
export function Fuentes({ data }: { data: DashboardData }) {
  const run = data.ultima_corrida;
  const coverage = data.cobertura;
  let dayWord = 'días';
  if (coverage.dias === 1) {
    dayWord = 'día';
  }
  const basketToday = data.canasta.hoy;

  return (
    <main className="page">
      <section className="intro">
        <h1>De dónde sale cada número</h1>
        <p className="lead">
          Todo el código, las reglas de la canasta y los datos históricos están en el repositorio. Cada corrida queda registrada, y los datos armados a mano llevan la fuente de cada fila.
        </p>
      </section>

      <section className="kpis three">
        <div className="card kpi">
          <span className="kpi-label">Última recolección</span>
          {run && (
            <>
              <span className="kpi-text">{boliviaTime(run.iniciada_en)}</span>
              <span className="status">
                <span className="status-dot" style={{ background: STATUS[run.estado].color }} />
                {STATUS[run.estado].label} · {run.precios.toLocaleString('es-BO')} precios
              </span>
            </>
          )}
          {!run && <span className="kpi-text">Sin corridas registradas</span>}
        </div>
        <div className="card kpi">
          <span className="kpi-label">Cobertura</span>
          <span className="kpi-text">
            {coverage.sucursales} sucursales · {coverage.productos.toLocaleString('es-BO')} productos
          </span>
          <span className="kpi-note">
            Canasta: {basketToday?.items ?? 0} de {data.canasta.items_total} productos con precio
          </span>
        </div>
        <div className="card kpi">
          <span className="kpi-label">Días de historial en el súper</span>
          <span className="kpi-text">{coverage.dias} {dayWord}</span>
          {coverage.primer_dia && <span className="kpi-note">desde el {shortDate(coverage.primer_dia)}</span>}
        </div>
      </section>

      <section className="card figure">
        <h2>Fuentes</h2>
        <div className="table-scroll">
          <table className="table stack">
            <thead>
              <tr>
                <th scope="col">Fuente</th>
                <th scope="col">Qué se toma</th>
                <th scope="col">Frecuencia</th>
                <th scope="col">Cómo</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Hipermaxi</th>
                <td data-label="Qué se toma">Precio, oferta y stock de las sucursales de Cochabamba</td>
                <td data-label="Frecuencia">Diaria</td>
                <td data-label="Cómo">API pública de la tienda en línea</td>
              </tr>
              <tr>
                <th scope="row">Banco Central de Bolivia</th>
                <td data-label="Qué se toma">Tipo de cambio oficial</td>
                <td data-label="Frecuencia">Diaria</td>
                <td data-label="Cómo">PDF anual de cotizaciones</td>
              </tr>
              <tr>
                <th scope="row">Defensoría del Pueblo</th>
                <td data-label="Qué se toma">Precios de mercado de 21 alimentos</td>
                <td data-label="Frecuencia">Mensual (2024–2025)</td>
                <td data-label="Cómo">Tablas de sus informes en PDF</td>
              </tr>
              <tr>
                <th scope="row">CEED de CADECOCRUZ</th>
                <td data-label="Qué se toma">Dólar paralelo (aproximado)</td>
                <td data-label="Frecuencia">Mensual (2024–2025)</td>
                <td data-label="Cómo">Variaciones de sus boletines semanales</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="row">
        <div className="card figure grow-even">
          <h2>Cómo se calcula la canasta</h2>
          <ol className="prose-list">
            <li>Cada producto de la canasta de la Defensoría tiene reglas que reconocen sus equivalentes en Hipermaxi (por nombre, subcategoría y presentación).</li>
            <li>Cada precio se lleva a Bs por kilo, litro o unidad.</li>
            <li>
              Por producto, sucursal y día se toma la <strong>mediana</strong> (precio típico) y el <strong>mínimo</strong> (lo más barato).
            </li>
            <li>Se multiplica por la cantidad semanal de la Defensoría (familia de {data.canasta.personas}) y se suma.</li>
          </ol>
        </div>
        <div className="card figure grow-even">
          <h2>Supuestos y límites</h2>
          <ul className="prose-list">
            <li>1 libra = 460 g. 1 cuartilla = 6 libras: con ese valor se reproduce el costo oficial de la canasta de la Defensoría.</li>
            <li>No todas las sucursales publican frutas y verduras en línea, y el plátano (banano) no aparece en ninguna. El costo de la ciudad junta los productos de todas las sucursales; entre sucursales se comparan solo los productos comunes.</li>
            <li>El sondeo de la Defensoría es ruidoso de un mes a otro: se leen tendencias, no meses sueltos.</li>
            <li>El paralelo es aproximado: cada fuente lo mide distinto.</li>
          </ul>
        </div>
      </section>

      <p className="footnote">
        Código y datos: <a href={REPOSITORY}>github.com/mateomerino14/OBSERVATORIO-PRECIOS-CBBA</a> · Datos generados el {boliviaTime(data.generado_en)}
      </p>
    </main>
  );
}
