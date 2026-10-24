import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 生产构建默认挂在 /admin（后端静态托管）；Docker 由 Nginx 在根路径提供，构建时传 ADMIN_BASE=/。
const adminBase = process.env.ADMIN_BASE ?? '/admin/'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  base: command === 'build' ? adminBase : '/',
  plugins: [
    vue(),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
}))
