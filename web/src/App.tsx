// Carga los datos y muestra la pantalla que indica el hash de la URL.

import { useEffect, useState } from 'react';
import { Header, type Route } from './components/Layout';
import { Fuentes } from './pages/Fuentes';
import { Modelos } from './pages/Modelos';
import { Productos } from './pages/Productos';
import { Resumen } from './pages/Resumen';
import { SuperVsMercado } from './pages/SuperVsMercado';
import type { DashboardData } from './types';

const DATA_URL = `${import.meta.env.BASE_URL}data/dashboard.json`;
const ROUTES: Route[] = ['resumen', 'super-vs-mercado', 'productos', 'modelos', 'fuentes'];
const TITLES: Record<Route, string> = {
  resumen: 'Resumen',
  'super-vs-mercado': 'Súper vs. mercado',
  productos: 'Productos',
  modelos: 'Modelos',
  fuentes: 'Fuentes y método',
};

/** Pantalla según el hash ("#/productos"); la de inicio si no coincide. */
export function routeFromHash(hash: string): Route {
  const candidate = hash.replace(/^#\/?/, '') as Route;
  if (ROUTES.includes(candidate)) {
    return candidate;
  }
  return 'resumen';
}

export function App() {
  const [route, setRoute] = useState<Route>(routeFromHash(window.location.hash));
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onChange = () => {
      setRoute(routeFromHash(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  useEffect(() => {
    document.title = `${TITLES[route]} — Observatorio de Precios CBBA`;
  }, [route]);

  useEffect(() => {
    fetch(DATA_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json() as Promise<DashboardData>;
      })
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  return (
    <div className="site">
      <Header current={route} />
      {error && (
        <main className="page">
          <p className="notice" role="alert">
            No se pudieron cargar los datos ({error}). Intenta recargar la página.
          </p>
        </main>
      )}
      {!data && !error && (
        <main className="page" aria-busy="true">
          <p className="notice">Cargando datos…</p>
        </main>
      )}
      {data && route === 'resumen' && <Resumen data={data} />}
      {data && route === 'super-vs-mercado' && <SuperVsMercado data={data} />}
      {data && route === 'productos' && <Productos data={data} />}
      {data && route === 'modelos' && <Modelos data={data} />}
      {data && route === 'fuentes' && <Fuentes data={data} />}
    </div>
  );
}
