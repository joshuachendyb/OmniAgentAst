import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

/**
 * 临时验证用 vite 配置（2026-10-08 小欧，验证完删除，不入库）
 * 与 vite.e2e.config.ts 同构，仅 5173→5273、proxy 上游 9000→9002（代理指向本 worktree 后端 8010）
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, '../src') },
  },
  server: {
    port: 5273,
    strictPort: true,
    hmr: false,
    proxy: {
      '/api': { target: 'http://localhost:9002', changeOrigin: true },
    },
  },
});
