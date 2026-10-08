import { defineConfig, devices } from '@playwright/test';

/**
 * 临时验证配置（2026-10-08 小欧，验证完删除，不入库）
 * baseURL 必须显式指向本 worktree 的 vite 5273（默认 5173 是另一会话的前端，不含插话代码）
 */
export default defineConfig({
  testDir: '.',
  testMatch: /fre2e_2\d_.*\.spec\.ts/,
  timeout: 900_000,
  expect: { timeout: 15_000 },
  reporter: [['line']],
  use: {
    baseURL: 'http://localhost:5273',
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
    headless: false,
    viewport: { width: 1600, height: 950 },
    // slowMo 在 Playwright 需走 launchOptions, 直接放 use 会 TS2769
    launchOptions: { slowMo: 250 },
    trace: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
