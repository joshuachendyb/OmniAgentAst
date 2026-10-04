// shot_observation_ui.mjs - 小欧 2026-10-04 - 抓 observation 展开区(结论区)真实 UI 截图(亮/暗两态)
//   用法: node shot_observation_ui.mjs
//   说明: 发一条会触发 listdir 的真实任务, 等工具结果到达(子行出现)后点开展开区并截全页。
import { chromium } from 'playwright';
import fs from 'fs';

const OUT = 'e2e_case/output/ui-shots';
fs.mkdirSync(OUT, { recursive: true });

const run = async (dark) => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    colorScheme: dark ? 'dark' : 'light',
  });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  if (dark) {
    await page.evaluate(() => {
      document.documentElement.classList.add('dark');
      document.body.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    });
    await page.waitForTimeout(800);
  }
  const tag = dark ? 'dark' : 'light';
  const input = page.locator('textarea').first();
  await input.fill(
    '请用 listdir 列出 F:\\OmniAgentAs-repair\\backend\\app\\utils 目录的内容'
  );
  await input.press('Enter');
  // 等"工具子行"出现: 必须是含工具名的可点行(页面上另有 aria-expanded 的无关元素, 不能只按属性等)
  const sub = page
    .locator('[role="button"][aria-expanded]')
    .filter({ hasText: /listdir|tree|read|searchtool|bash/ })
    .first();
  await sub.waitFor({ state: 'visible', timeout: 240000 });
  await page.waitForTimeout(2000);
  await sub.click();
  await page.waitForTimeout(1500);
  // 结论区内容断言(状态点+完整摘要+metrics标签; data_text/工具名不应出现)
  const expandedText = await page
    .locator('[role="button"][aria-expanded="true"]')
    .first()
    .innerText()
    .catch(() => '(未取到)');
  console.log(`[${tag}] 展开区文本:`, JSON.stringify(expandedText));
  const f = `${OUT}/observation-${tag}.png`;
  await page.screenshot({ path: f, fullPage: true });
  console.log('SHOT', f);
  await browser.close();
};

await run(false);
await run(true);
