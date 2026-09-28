/**
 * e2e_case/vite.isolated.config.ts — 配置类 E2E 专用 vite（前端 :5174） — 小欧 2026-09-28
 *
 * 存在的理由：fre2e_08/09/10/11/12 是「写配置」用例（POST/PUT/DELETE /providers、/models、
 * /settings），页面点「保存」经 vite proxy 直达后端 → 落 config.yaml。
 * 原先它们与跑任务的用例共用 :5173 + :8000，于是测试值写真配置。实测污染过：
 *   ① fre2e_11 用例 34/36 把当前 provider(sensenova) 的 label 改成「E2E测试标签」、
 *      api_base 改成 https://api.e2e-test.example.com/v1，靠「改回原值」补救——
 *      进程中途被杀就永久留下（2026-09-28 09:19 实测发生）。
 *   ② e2e-del-20260928-091908 这类删除用例顺手加的模型也进了真配置。
 * 「事后还原」不是可靠机制（AGENTS.md 配置隔离铁律：根治靠「够不到」）。
 *
 * 本配置让写配置用例拥有一条独立链路，物理上够不到真配置：
 *   浏览器 → vite :5174（本文件，hmr:false 免 full-reload 销毁页面上下文）
 *          → 代理 :9001（api-proxy.ts，PROXY_TARGET 指向隔离后端）
 *          → 隔离后端 :8898（OMNIAGENT_CONFIG_PATH 指向 config 临时副本）
 *
 * 与 vite.e2e.config.ts（断流重连 case 用，:5173→:9000→:8000）刻意并存、互不干扰。
 * 编辑历史: 2026-09-28 小欧 - 初创（配置类 E2E 配置隔离，配套 e2e_front_lib/isolated-env.ts）
 */
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// 2026-09-28 小欧 - 端口与 isolated-env.ts 单源约定：5174 页面 / 9001 代理 / 8898 隔离后端
//   （改端口只改 isolated-env.ts 一处；本文件代理 target 随之改，勿各改一半）
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, '../src') },
  },
  server: {
    port: 5174,
    strictPort: true,
    hmr: false,
    proxy: {
      // → 独立代理 :9001 → 隔离后端 :8898（不经过共享 :9000，避免与跑任务用例的 :8000 链路混用）
      '/api': { target: 'http://localhost:9001', changeOrigin: true },
    },
  },
});
