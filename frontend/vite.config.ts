import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * In development the front end runs on its own Vite server, so every path owned
 * by the backend is proxied to it. In production a single FastAPI process serves
 * both the API and this build output — see backend/src/lupus_ex_machina/web.
 */
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'
const BACKEND_PATHS = ['/api', '/models', '/health']

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      BACKEND_PATHS.map((path) => [path, { target: BACKEND_ORIGIN, changeOrigin: true }]),
    ),
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
