// 2026-10-22 小欧 - 应用内字体生效实测(临时): 直接量 5173 页面里的 var(--font-mono) 解析结果
import { chromium } from '@playwright/test';

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);

const res = await page.evaluate(() => {
  const rootVar = getComputedStyle(document.documentElement).getPropertyValue(
    '--font-mono'
  );
  // 探针: 用与代码块完全相同的 font-family 声明, 量各字符的实际显示宽
  const probe = document.createElement('pre');
  probe.style.cssText =
    'font-family: var(--font-mono, monospace); font-size: 40px; line-height: 1; white-space: pre; margin:0;';
  document.body.appendChild(probe);
  const measure = (t: string) => {
    probe.textContent = t;
    const node = probe.firstChild as Text;
    const r = document.createRange();
    r.setStart(node, 0);
    r.setEnd(node, t.length);
    return r.getBoundingClientRect().width;
  };
  const latin = measure('A');
  const out: Record<string, number | string> = {
    '--font-mono 变量值': rootVar.trim() || '(未定义!)',
    'Latin(A)px': +latin.toFixed(2),
  };
  for (const ch of ['─', '│', '▶', '▲', '感']) {
    out[ch] = +(measure(ch) / latin).toFixed(3);
  }
  probe.remove();
  return out;
});

console.log(JSON.stringify(res, null, 2));
console.log(
  '\n判据: 框线=1.000 / ▶=1.000 / 感=2.000 → 页面已用 Sarasa; 否则 = 未生效'
);
await browser.close();
