import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";

// https://vite.dev/config/
export default defineConfig({
  base: './',
  server: {
    host: '127.0.0.1',
    port: 5173,
    open: true,
  },
  build: {
    sourcemap: false,
  },
  plugins: [
    react(),
    tsconfigPaths()
  ],
})
