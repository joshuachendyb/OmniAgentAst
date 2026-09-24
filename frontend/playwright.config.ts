/**
 * Playwright Configuration
 *
 * @author 小新
 * @description E2E testing configuration for Playwright
 */

import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E testing
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e_case',

  /* Run tests in files in parallel */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,

  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,

  /* Opt out of parallel tests on CI */
  workers: 1,

  /* Reporter to use: html 报告与测试产物统一落 e2e_case/output/（与 DIAG/代理日志同一根目录）
     编辑历史: 2026-09-13 小欧 - 前端E2E日志/产物统一落盘规范: Playwright 产物根移入 e2e_case/output - 小欧-2026-09-13
     编辑历史: 2026-09-25 04:06:45 小健 - E2E 串行化: workers 本地由 undefined 改强制 1（原仅 CI 限 1，本地并行致真实后端探针互踩/残留） - 小健-2026-09-25 */
  reporter: [
    [
      'html',
      { outputFolder: './e2e_case/output/playwright-report', open: 'never' },
    ],
  ],

  /* 测试产物根(截图/视频/trace 等)统一落 e2e_case/output/ 编辑历史: 2026-09-13 小欧 */
  outputDir: './e2e_case/output/test-results',

  /* Shared settings for all the projects below */
  use: {
    /* Base URL to use in actions like `await page.goto('/')` */
    baseURL: 'http://localhost:5173',

    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',

    /* Screenshot on failure */
    screenshot: 'only-on-failure',

    /* Video recording */
    video: 'on-first-retry',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Run local dev server before starting the tests */
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
