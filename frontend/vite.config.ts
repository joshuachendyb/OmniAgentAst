// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复配置对象属性换行/缩进统一, 防止格式再次出错
// 编辑历史: 2026-09-22 小欧 - server.port/proxy 补注释说明前端:5173→后端:8000 端口关系(两种连接方式 + 改端口同步清单)
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import eslint from 'vite-plugin-eslint';
import prettier from 'vite-plugin-prettier';
import { visualizer } from 'rollup-plugin-visualizer';
import path from 'path';

// https://vitejs.dev/config/
// 【小强 2026-04-21】性能优化：
//   1. 添加 terser 生产压缩（drop_console/drop_debugger）
//   2. 修正 chunkSizeWarningLimit 统一为 1000
//   3. 添加 optimizeDeps 加速冷启动预构建
//   4. 注：antd v5 已原生支持 Tree-shaking，无需 vite-plugin-style-import
export default defineConfig(({ command }) => {
  const isBuild = command === 'build';
  const shouldCheck = isBuild;

  return {
    plugins: [
      react(),
      shouldCheck && eslint(),
      shouldCheck &&
        prettier({
          parser: 'typescript',
        }),
      isBuild &&
        visualizer({
          filename: 'dist/stats.html',
          open: false,
          gzipSize: true,
          brotliSize: true,
        }),
    ].filter(Boolean),
    // ⚠️ 警告：禁止删除 resolve.alias！@/ 别名被所有 renderers 使用，删除会导致全前端 500 错误（历史教训 2026-05-23）
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      // 前端 dev server 端口（Vite 默认 5173）。
      // 端口关系：前端(:5173) → 后端(:8000)，两种连接方式：
      //   方式1 proxy：下方 proxy 配置将 /api/* 转发到 localhost:8000（同源，无 CORS）
      //   方式2 直连：getApiBaseUrl() 拼 hostname:port 直连后端（走 CORS，需改 constants.py 白名单）
      // 改端口须同步：proxy.target（方式1）或 VITE_API_PORT + CORS 白名单（方式2）
      port: 5173,
      proxy: {
        // Vite 内置 http-proxy：开发模式下 /api/* 请求代理到后端 uvicorn(:8000)。
        // 改后端端口时同步改 target。生产构建不走此 proxy（由 Nginx/反代接管）。
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      // 手动分 chunk：大库分离到独立文件，利用浏览器缓存
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-antd': ['antd'],
            'vendor-utils': ['axios', 'dayjs'],
          },
        },
      },
      cssCodeSplit: true,
      // 【小强 2026-04-21】统一为 1000KB，antd 分包后单 chunk 体积约 800KB
      chunkSizeWarningLimit: 1000,
      // 【小强 2026-04-21】生产构建压缩：移除 console/debugger，减少包体积
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: true,
          drop_debugger: true,
        },
      },
      // 报告 gzip/brotli 压缩后实际大小
      reportCompressedSize: true,
    },
    // 【小强 2026-04-21】预构建优化：开发模式冷启动加速
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        'antd',
        'axios',
        'dayjs',
      ],
    },
  };
});
