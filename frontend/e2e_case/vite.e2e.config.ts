import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// E2E 断线重连测试专用 vite 配置 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 初创(断连E2E根因): 断流手段"杀vite→重启"时, 默认 dev vite 会向页面推送
//   server restarted → full-reload, 销毁已加载页面的 JS 上下文 → 已排队的 GET#2/3 重连 setTimeout 随之死亡,
//   二次重连永不发生(取证见手册 9.x)。真实部署前端经 nginx, "网关/静态代理重启"不会 reload 已加载页面;
//   本配置 hmr:false 消除该 dev 特有人工副作用, 最贴近真实断线重连语义。
//   其余(react插件/alias/@/server.port/proxy:/api)与项目 vite.config.ts 对齐。
// 编辑历史: 2026-09-13 小欧 - proxy '/api' 上游改为独立代理(9000→8000, e2e_case/api-proxy.ts):
//   "进程分离"方案核心。直接 target 8000 只断 vite 才能断流(波及页面源, 触发vite client reload);
//   经独立代理后, 断流只 kill 9000 进程 → 页面(vite:5173)永活不 reload → 重连 timer 存活 → 续传必达。
// 编辑历史: 2026-09-13 小欧 - 迁移: tests/e2e → e2e_case; alias @ 由 ../../src 改 ../src(目录层级变化) - 小欧-2026-09-13
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, '../src') },
  },
  server: {
    port: 5173,
    strictPort: true,
    hmr: false,
    proxy: {
      '/api': { target: 'http://localhost:9000', changeOrigin: true },
    },
  },
});