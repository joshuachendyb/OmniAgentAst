// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复配置对象属性换行/缩进统一, 防止格式再次出错
// 编辑历史: 2026-09-22 小欧 - server.port/proxy 补注释说明前端:5173→后端:8000 端口关系(两种连接方式 + 改端口同步清单)
// 编辑历史: 2026-09-23 小欧 - server.watch.usePolling=true: Windows 下 chokidar 长跑丢文件事件
//   (2026-09-23 一天连发两次"改代码浏览器不生效"根因)，轮询监听根治，代价=多耗 CPU - 小欧-2026-09-23
// 2026-09-26 小欧 - 配套改造: server.host 补 '0.0.0.0'。此前未配 host → Vite 默认只绑 localhost
//   (Windows 解析为 [::1] IPv6 回环) → **局域网其他机器访问不到前端**(后端 uvicorn 已是 0.0.0.0, 两端不对齐)。
//   依据部署事实: 后端在 B 机器、客户端在局域网多台机器, 前端必须对外可达。
//   连带: e2e_case/vite.e2e.config.ts 仍绑 ::1(测试专用, 有意不对外暴露, 不改)。 — 小欧-2026-09-26
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
      // 端口关系：前端(:5173) → 后端(:8000)，默认走下方 proxy（/api/* → localhost:8000，同源无 CORS）。
      // 前端 REST 与 SSE 均为相对路径 /api/v1（修复：此前 REST 直连、SSE 相对，
      // 两条通道分叉）。前后端不同源且无反代时才设 VITE_API_BASE_URL 显式指向后端。
      // 改端口须同步：proxy.target 与 VITE_API_BASE_URL。
      port: 5173,
      // 2026-09-26 小欧 - 配套改造: 绑 0.0.0.0 与后端 uvicorn(--host 0.0.0.0)对齐。
      //   此前未配 host，Vite 默认只绑 localhost(Windows 解析为 [::1] IPv6 回环)，
      //   导致**局域网其他机器访问不了前端**（后端 0.0.0.0 可达、前端不可达，两端不对齐）。
      //   部署事实: 后端在 B 机器、客户端在局域网多台机器 → 前端必须对外可达。
      //   注意: 这只影响 dev server；生产静态托管由部署方自行绑定。
      host: '0.0.0.0',
      watch: {
        // 【小欧 2026-09-23】轮询监听：Windows 下 chokidar push 通知长跑后会丢文件变更事件，
        // 导致"改了源码 vite 不热更、浏览器一直旧版"（当日连发两次，重启才恢复）。usePolling 根治，
        // 代价是固定间隔轮询 stat 多耗少量 CPU。
        usePolling: true,
      },
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
