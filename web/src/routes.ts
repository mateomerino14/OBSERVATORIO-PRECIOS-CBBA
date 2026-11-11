// Pantallas del sitio, en el orden de la navegación, y su lectura desde el hash de la URL.

export type Route = 'resumen' | 'super-vs-mercado' | 'productos' | 'modelos' | 'fuentes';

const HOME: Route = 'resumen';

export const SCREENS: { route: Route; label: string }[] = [
  { route: 'resumen', label: 'Resumen' },
  { route: 'super-vs-mercado', label: 'Súper vs. mercado' },
  { route: 'productos', label: 'Productos' },
  { route: 'modelos', label: 'Modelos' },
  { route: 'fuentes', label: 'Fuentes y método' },
];

/** Pantalla según el hash ("#/productos"); la de inicio si no coincide. */
export function routeFromHash(hash: string): Route {
  const candidate = hash.replace(/^#\/?/, '');
  const screen = SCREENS.find((item) => item.route === candidate);
  if (screen) {
    return screen.route;
  }
  return HOME;
}

/** Nombre visible de una pantalla. */
export function screenLabel(route: Route): string {
  return SCREENS.find((item) => item.route === route)?.label ?? route;
}
