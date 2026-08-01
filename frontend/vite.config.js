import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
  },
  preview: {
    host: '0.0.0.0',
    port: Number(process.env.PORT) || 4173,
    allowedHosts: ['terramind-smarter-farming-every-stage.onrender.com'],
  },
  build: {
    rollupOptions: {
      output: {
        /**
         * Only libraries genuinely in the critical path are named here.
         *
         * recharts, jspdf and react-markdown were previously listed too, which
         * was actively harmful: naming a manual chunk pulls it into the entry's
         * static graph, so Vite emitted <link rel="modulepreload"> for ~700 kB
         * of JS the landing page never executes, defeating the lazy `import()`
         * boundaries around them. Left alone, Rollup already emits a separate
         * on-demand chunk per dynamic import.
         */
        /**
         * Function form, not the object form. Vite 8 bundles with Rolldown,
         * which only accepts a function here — the object shorthand fails the
         * build outright with "manualChunks is not a function".
         *
         * Paths are matched with separators on both sides so that, for example,
         * `/react/` cannot also swallow `react-markdown` or `react-router`.
         */
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('/scheduler/') ||
            id.includes('/react-router/') ||
            id.includes('/react-router-dom/')
          ) {
            return 'react-vendor';
          }
          if (id.includes('/framer-motion/') || id.includes('/motion-dom/') || id.includes('/motion-utils/')) {
            return 'motion';
          }
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
});
