import { chromium } from '@playwright/test';

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto('about:blank');

const data = await page.evaluate(() => {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  const measure = (font, ch) => {
    ctx.font = '40px ' + font;
    return ctx.measureText(ch).width;
  };
  const stacks = [
    ['当前: Consolas, Menlo, monospace', 'Consolas, Menlo, monospace'],
    ['甲: Consolas, DejaVu, Cascadia, Menlo', "Consolas, 'DejaVu Sans Mono', 'Cascadia Mono', Menlo, monospace"],
    ['乙: Sarasa, DejaVu, Consolas, Menlo', "'Sarasa Mono SC', 'DejaVu Sans Mono', Consolas, Menlo, monospace"],
    ['丙: Cascadia, DejaVu, Consolas', "'Cascadia Mono', 'DejaVu Sans Mono', Consolas, monospace"],
  ];
  const chars = ['A', '─', '│', '┌', '┐', '▶', '▲', '▼', '→', '感'];
  const out = {};
  for (const [name, stack] of stacks) {
    out[name] = {};
    for (const ch of chars) out[name][ch] = measure(stack, ch);
  }
  return out;
});

for (const [name, m] of Object.entries(data)) {
  const r = (ch) => (m[ch] / m['A']).toFixed(3);
  console.log(
    name.padEnd(42) +
      ' ASCII=1  ─=' + r('─') + ' │=' + r('│') + ' ┌=' + r('┌') +
      ' ▶=' + r('▶') + ' ▲=' + r('▲') + ' ▼=' + r('▼') + ' →=' + r('→') +
      ' 感=' + r('感')
  );
}
await browser.close();
