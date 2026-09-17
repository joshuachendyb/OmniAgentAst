/**
 * e2e_case/e2e.config.ts — 前端 E2E 全局配置 — 小欧 2026-09-13
 *
 * 【浏览器"跑完是否自动退出"开关 — 双通道，看情况任选】
 *   - false(默认): 测试跑完浏览器自动关闭（框架行为；多 case 连跑 / CI 用它）
 *   - true       : 测试跑完浏览器不关闭、页面停住供查看（仅适合单 case 调试），
 *                  查看完毕按 Ctrl+C 结束；或改回 false 恢复自动关闭。
 *   —— 改动此文件一行 = 常驻偏好；
 *   —— 命令行 `set "KEEP_BROWSER=1"&& npx playwright test <case> --headed` = 临时一次(优先级更高，不改文件)
 */
export const E2E_KEEP_BROWSER_OPEN = false;
