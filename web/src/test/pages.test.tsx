import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Fuentes } from '../pages/Fuentes';
import { Modelos } from '../pages/Modelos';
import { Productos } from '../pages/Productos';
import { Resumen } from '../pages/Resumen';
import { SuperVsMercado } from '../pages/SuperVsMercado';
import type { DashboardData } from '../types';
import fixture from './dashboard.fixture.json';

// Copia real de `observatorio exportar` (8 nov 2026, dos sucursales).
const data = fixture as unknown as DashboardData;

describe('pantallas con datos reales', () => {
  it('resumen muestra la canasta del día y el dólar', () => {
    render(<Resumen data={data} />);
    expect(screen.getByText('Bs 193,34')).toBeInTheDocument();
    expect(screen.getByText('Bs 11,71')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Costo semanal de la canasta/ })).toBeInTheDocument();
    expect(screen.getByText('Tomate')).toBeInTheDocument();
  });

  it('resumen compara sucursales solo sobre los productos comunes', () => {
    render(<Resumen data={data} />);
    expect(screen.getByText('La canasta en cada sucursal')).toBeInTheDocument();
    expect(screen.getByText(/sobre los 8 productos que tienen todas/)).toBeInTheDocument();
    expect(screen.getAllByText(/8 de 13 productos en línea/)).toHaveLength(2);
  });

  it('súper vs. mercado lista productos de mayor a menor diferencia', () => {
    render(<SuperVsMercado data={data} />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByRole('rowheader')).toHaveTextContent('Fideo corto');
    expect(within(rows.at(-1)!).getByRole('rowheader')).toHaveTextContent('Azúcar');
    expect(screen.getByText(/Los precios subieron con el dólar/)).toBeInTheDocument();
  });

  it('productos cambia de producto y de sucursal', () => {
    render(<Productos data={data} />);
    fireEvent.change(screen.getByLabelText('Producto'), { target: { value: 'arroz' } });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Arroz de primera');
    const branch = screen.getByRole('button', { name: 'Blanco Galindo' });
    fireEvent.click(branch);
    expect(branch).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(/El historial diario se está juntando/)).toBeInTheDocument();
  });

  it('productos abre en un producto que el súper vende', () => {
    render(<Productos data={data} />);
    expect(screen.getByRole('heading', { level: 1 })).not.toHaveTextContent('Papaya');
  });

  it('productos sin precio en línea lo dicen', () => {
    render(<Productos data={data} />);
    fireEvent.change(screen.getByLabelText('Producto'), { target: { value: 'papaya' } });
    expect(screen.getByText('Hipermaxi no publica este producto en línea')).toBeInTheDocument();
  });

  it('fuentes muestra cobertura y método', () => {
    render(<Fuentes data={data} />);
    expect(screen.getByText(/2 sucursales/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Cómo se calcula la canasta' })).toBeInTheDocument();
  });

  it('modelos muestra la evaluación, sugerencias con su motivo y saltos de mercado', () => {
    render(<Modelos data={data} />);
    expect(screen.getByText('83 %')).toBeInTheDocument();
    expect(screen.getByText(/99 de 119/)).toBeInTheDocument();
    const fideo = screen.getByRole('heading', { name: /Fideo corto/ }).closest('section')!;
    expect(within(fideo).getAllByText('presentación fuera de rango').length).toBeGreaterThan(0);
    expect(within(fideo).getAllByText('aceptado, poco parecido al resto').length).toBeGreaterThan(0);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByRole('rowheader')).toHaveTextContent('Pulpa de res');
    expect(screen.getByText('Se activa con 8 días de precios')).toBeInTheDocument();
  });

  it('modelos muestra los grupos de k-means con su elección de k', () => {
    render(<Modelos data={data} />);
    expect(screen.getByRole('img', { name: /coloreados por grupo/ })).toBeInTheDocument();
    const stable = screen.getByRole('heading', { name: 'Estables' }).closest('li')!;
    expect(within(stable).getByText(/Arroz/)).toBeInTheDocument();
    const jumped = screen.getByRole('heading', { name: 'Saltaron con la subida del dólar' }).closest('li')!;
    expect(within(jumped).getByText('Cebolla, Harina de trigo')).toBeInTheDocument();
    expect(screen.getByText(/k = 3, la silueta más alta \(0,39; con 2: 0,35/)).toBeInTheDocument();
  });

  it('modelos lista saltos del súper cuando hay historial', () => {
    const withHistory: DashboardData = {
      ...data,
      anomalias: {
        ...data.anomalias,
        super: {
          ...data.anomalias.super,
          dias: 10,
          items: [
            {
              nombre: 'Aceite Fino 900 ml',
              sucursal: 'HIPERMAXI SACABA',
              precio: 12,
              mediana_previa: 20,
              dias_previos: 9,
              cambio_pct: -40,
              oferta: true,
            },
          ],
        },
      },
    };
    render(<Modelos data={withHistory} />);
    expect(screen.getByText('Aceite Fino 900 ml')).toBeInTheDocument();
    expect(screen.getByText('en oferta')).toBeInTheDocument();
    expect(screen.getByText('−40 %')).toBeInTheDocument();
  });
});
