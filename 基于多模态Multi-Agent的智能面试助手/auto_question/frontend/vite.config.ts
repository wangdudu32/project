import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '')
  return {
    envDir: '..',
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: Number(env.FRONTEND_PORT || 5173),
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY || 'http://127.0.0.1:' + (env.BACKEND_PORT || '8000'),
          changeOrigin: true,
          rewrite: path => path.replace(/^\/api/, ''),
          timeout: 900_000,
          proxyTimeout: 900_000,
        },
      },
    },
  }
})
