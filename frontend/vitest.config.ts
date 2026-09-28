/**
 * Vitest Configuration
 *
 * @author 小新
 * @description Testing configuration for frontend unit tests
 */

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.ts'],
    // 2026-09-28 小欧 - 挂 live 隔离后端 harness：live-* 用例原直连开发后端 :8000，
    //   可写闭环类直接写真配置（已污染 4 次）。harness 拉专用后端（OMNIAGENT_CONFIG_PATH
    //   指临时副本）让真配置够不到；无 live 过滤的纯单测跑不拉起，不额外依赖 Python/端口。
    globalSetup: ['./src/tests/support/liveBackend.ts'],
    include: ['src/tests/**/*.{test,spec}.{ts,tsx}'], // 只运行我们自己的测试
    exclude: ['e2e_case/**', 'node_modules/**'], // 排除E2E测试和node_modules
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
      exclude: [
        'node_modules/',
        'src/tests/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData.ts',
      ],
    },
  },
});
