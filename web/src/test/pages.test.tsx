import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Fuentes } from '../pages/Fuentes';
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
    expect(screen.getByText('Bs 193,44')).toBeInTheDocument();
    expect(screen.getByText('Bs 11,71')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Costo semanal de la canasta/ })).toBeInTheDocument();
    expect(screen.getByText('Tomate')).toBeInTheDocument();
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
});
