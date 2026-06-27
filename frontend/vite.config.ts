import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  base: '/spreadfleet/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/spreadfleet/api': {
        target: 'http://127.0.0.1:9092',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/spreadfleet/, ''),
      },
    },
  },
})
