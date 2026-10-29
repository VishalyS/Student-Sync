import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/login': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/register': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/profile': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/stats': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/notifications': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/send-message': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/update': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  }
})
