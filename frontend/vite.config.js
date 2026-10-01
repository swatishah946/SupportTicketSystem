import process from 'node:process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy /api and /admin to Django so the browser sees one origin:
// httpOnly auth cookies then work without cross-site cookie gymnastics,
// exactly like production where nginx does the same job.
const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target, changeOrigin: false },
      '/ws': { target, changeOrigin: false, ws: true },
      '/admin': { target, changeOrigin: false },
      '/static': { target, changeOrigin: false },
    },
  },
})
