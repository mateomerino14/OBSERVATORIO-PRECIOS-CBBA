import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Rutas relativas para que el sitio funcione en GitHub Pages bajo /OBSERVATORIO-PRECIOS-CBBA/.
export default defineConfig({
  base: './',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
