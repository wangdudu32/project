import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || '/api'
  return {
    server: {
      port: Number(env.VITE_PORT || 5183),
      host: '127.0.0.1',
      strictPort: true,
      proxy: {
        [apiBase]: {
          target: env.VITE_API_PROXY || 'http://127.0.0.1:8001',
          changeOrigin: true,
          rewrite: (path: string) => path.slice(apiBase.length) || '/',
          timeout: 900_000,
          proxyTimeout: 900_000,
        },
      },
    },
    resolve: { alias: [{ find: /^@\//, replacement: '/src/' }] },
    plugins: [react()],
  }
})
