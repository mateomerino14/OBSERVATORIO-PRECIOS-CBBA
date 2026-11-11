// Pantalla 3: detalle de un producto de la canasta.

import { INK, PRICE } from '../colors';
import { useState } from 'react';
import { Bar, EmptyState, Figure, KpiCard } from '../components/Layout';
import { LineChart } from '../components/LineChart';
import { branchLabel, money, number, shortDate, shortMonth } from '../format';
import { ALL_BRANCHES, dailySeries } from '../series';
import type { DashboardData } from '../types';

const MIN_DAYS_FOR_LINE = 2;


/** Pantalla de un producto de la canasta: historia y productos de tienda. */
export function Productos({ data }: { data: DashboardData }) {
  // Se abre en el primer producto que el súper vende; si ninguno, en el primero.
  const firstPriced = data.productos.find((item) => item.hoy !== null) ?? data.productos[0];
  const [code, setCode] = useState(firstPriced?.codigo ?? '');
  const [branch, setBranch] = useState(ALL_BRANCHES);
  const [query, setQuery] = useState('');

  const branches = [ALL_BRANCHES, ...new Set(data.canasta.por_sucursal.map((row) => row.sucursal))];
  const normalized = query.trim().toLowerCase();
  const options = data.productos.filter((product) => normalized === '' || product.nombre.toLowerCase().includes(normalized));
  const product = data.productos.find((item) => item.codigo === code) ?? data.productos[0];

  if (!product) {
    return (
      <main className="page">
        <EmptyState title="Todavía no hay productos" />
      </main>
    );
  }

  const unit = product.unidad_visible;
  const lastMarket = product.mercado_mensual.at(-1);
  const daily = dailySeries(product, branch);
  const dailyValues = daily.values;
  const marketPrices = product.mercado_mensual.map((row) => row.precio);
  const allPrices = [...marketPrices, ...dailyValues];
  if (product.hoy) {
    allPrices.push(product.hoy.tipico, product.hoy.minimo);
  }
  const step = Math.max(1, 10 ** Math.floor(Math.log10(Math.max(...allPrices, 1))) / 2);
  const yMin = Math.floor(Math.min(...allPrices) / step) * step;
  const yMax = Math.ceil(Math.max(...allPrices) / step) * step;
  const ticks = [yMin, (yMin + yMax) / 2, yMax];
  const maxUnit = Math.max(...product.tienda.map((item) => item.precio_unidad), 1);

  let marketLabel = 'Mercado';
  if (lastMarket) {
    marketLabel = `Mercado, ${shortMonth(lastMarket.mes)}`;
  }

  let quantityText = `${number(product.cantidad_canasta, 0)} ${product.unidad}`;
  if (product.unidad === 'u') {
    quantityText = `${number(product.cantidad_canasta, 0)} unidades`;
  }

  return (
    <main className="page">
      <section className="controls">
        <div className="field">
          <label htmlFor="buscar">Buscar producto de la canasta</label>
          <input id="buscar" type="search" value={query} placeholder="arroz, leche, pollo…" onChange={(event) => setQuery(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="producto">Producto</label>
          <select id="producto" value={product.codigo} onChange={(event) => setCode(event.target.value)}>
            {options.map((item) => (
              <option key={item.codigo} value={item.codigo}>
                {item.nombre}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div role="group" aria-label="Sucursal" className="pills">
        {branches.map((name) => (
          <button key={name} type="button" className="pill" aria-pressed={branch === name} onClick={() => setBranch(name)}>
            {branchLabel(name)}
          </button>
        ))}
      </div>

      <section className="intro">
        <h1>{product.nombre}</h1>
        <p className="lead small">
          Canasta de la Defensoría: {quantityText} por semana · precio típico = mediana de los {product.hoy?.productos ?? 0} productos emparejados
        </p>
      </section>

      <section aria-label={`Precio por ${unit}`} className="kpis">
        <KpiCard label="Súper, precio típico" value={money(product.hoy?.tipico)} unit={unit} tone="price" />
        <KpiCard label="Súper, más barato" value={money(product.hoy?.minimo)} unit={unit} />
        <KpiCard label={marketLabel} value={money(lastMarket?.precio)} unit={unit} />
        <KpiCard label="Días con precio en el súper" value={String(daily.days.length)} tone="muted" note={data.cobertura.primer_dia && `la recolección empezó el ${shortDate(data.cobertura.primer_dia)}`} />
      </section>

      <section className="row">
        <Figure className="grow" title={`Precio por ${unit}, día a día`} subtitle={`Precio típico · ${branchLabel(branch)}`}>
          {dailyValues.length < MIN_DAYS_FOR_LINE && (
            <EmptyState title="El historial diario se está juntando">La línea aparece desde el segundo día con datos.</EmptyState>
          )}
          {dailyValues.length >= MIN_DAYS_FOR_LINE && (
            <LineChart
              categories={daily.days}
              series={[{ id: 'diario', color: PRICE, width: 3, values: dailyValues }]}
              yMin={yMin}
              yMax={yMax}
              yTicks={ticks}
              xTicks={[
                { index: 0, label: shortDate(daily.days[0]) },
                { index: daily.days.length - 1, label: shortDate(daily.days[daily.days.length - 1]) },
              ]}
              ariaLabel={`Precio típico diario de ${product.nombre}`}
            />
          )}
        </Figure>
        <Figure className="side" title="En el mercado" subtitle={`Bs por ${unit} · Defensoría, mensual`}>
          {product.mercado_mensual.length === 0 && <EmptyState title="Sin datos de mercado para este producto" />}
          {product.mercado_mensual.length > 0 && (
            <LineChart
              categories={product.mercado_mensual.map((row) => row.mes)}
              series={[{ id: 'mercado', color: INK, values: marketPrices }]}
              yMin={yMin}
              yMax={yMax}
              yTicks={ticks}
              xTicks={[
                { index: 0, label: shortMonth(product.mercado_mensual[0].mes) },
                { index: product.mercado_mensual.length - 1, label: shortMonth(lastMarket?.mes ?? '') },
              ]}
              ariaLabel={`Precio de mercado mensual de ${product.nombre}`}
            />
          )}
        </Figure>
      </section>

      <Figure
        title={`Productos de Hipermaxi que cuentan como "${product.nombre.toLowerCase()}"`}
        subtitle={data.ultimo_dia && `${shortDate(data.ultimo_dia)} · precio más bajo entre sucursales, ordenados por Bs por ${unit}`}
        source="Las reglas de emparejamiento están en canastas/defensoria_semanal.toml."
      >
        {product.tienda.length === 0 && <EmptyState title="Hipermaxi no publica este producto en línea" />}
        {product.tienda.length > 0 && (
          <div className="table-scroll">
            <table className="table stack">
              <thead>
                <tr>
                  <th scope="col">Producto</th>
                  <th scope="col" className="num">Precio</th>
                  <th scope="col" className="num">Bs por {unit}</th>
                  <th scope="col" className="num">Sucursales</th>
                  <th scope="col" className="bar-col">
                    <span className="visually-hidden">Comparación</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {product.tienda.map((item) => (
                  <tr key={item.url}>
                    <th scope="row" className="plain">
                      <a href={item.url} target="_blank" rel="noreferrer">
                        {item.nombre}
                      </a>
                    </th>
                    <td className="num mono" data-label="Precio">{money(item.precio)}</td>
                    <td className="num mono" data-label={`Bs por ${unit}`}>{number(item.precio_unidad)}</td>
                    <td className="num mono" data-label="Sucursales">{item.sucursales}</td>
                    <td className="stack-hide">
                      <Bar value={item.precio_unidad} max={maxUnit} color={PRICE} />
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
