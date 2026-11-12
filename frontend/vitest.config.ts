/**
 * Vitest Configuration
 *    2026-11-06 小欧 - 附件域测试用例遵循项目既有约定落 src/tests/unit/
 *     (与全仓 .test.ts 统一), vitest include 维持只收录 src/tests/** — 小欧-2026-11-06
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
    // 2026-11-12 小欧 - 原「全量回归降噪」排除清单(4 个长期红项: useChatSend 发送链路 /
    //   link 开关 / 模型库页)已清空 —— 这 4 个用例的失败根因全是**用例过时**(漏传 SendOpts
    //   第二参 / 断言旧文案 / 审计式源码正则跟不上形态演进), 已逐个按现行契约改写并单跑通过,
    //   故重新纳入全量, 不留"永久排除"的尾巴。
    //   仍保留的排除项只有 e2e 与依赖目录 —— live-* 用例由 globalSetup 拉隔离后端(需 8899 端口空闲)。
    exclude: ['e2e_case/**', 'node_modules/**'],
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

