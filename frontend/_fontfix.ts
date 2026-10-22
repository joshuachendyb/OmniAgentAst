import { chromium } from '@playwright/test';
import { writeFileSync } from 'node:fs';

const ART = [
  '┌──────────────────────────────┐',
  '│ 感知        │───▶│ 规划     │',
  '│ Perception  │    │ Planning │',
  '└──────────────────────────────┘',
];

const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{background:#fff;margin:0;padding:12px;font-family:"Segoe UI","Microsoft YaHei",sans-serif}
h3{font-size:12px;margin:10px 0 2px;color:#444}
pre{font-size:17px;margin:0;white-space:pre;line-height:1.4}
.a{font-family:Consolas,Menlo,monospace}
.b{font-family:Consolas,"DejaVu Sans Mono","Cascadia Mono",Menlo,monospace}
</style></head><body>
<h3>当前栈: Consolas, Menlo, monospace</h3><pre class="a">${ART.join('\n')}</pre>
<h3>方案甲: Consolas, "DejaVu Sans Mono", "Cascadia Mono", Menlo, monospace（ASCII 仍是 Consolas）</h3><pre class="b">${ART.join('\n')}</pre>
</body></html>`;

writeFileSync('C:/Users/chend/AppData/Local/Temp/font-fix.html', html, 'utf-8');

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 620, height: 300 }, deviceScaleFactor: 1 });
await page.goto('file:///C:/Users/chend/AppData/Local/Temp/font-fix.html');
await page.waitForTimeout(300);
await page.screenshot({ path: 'C:/Users/chend/AppData/Local/Temp/font-fix.png', fullPage: true });
await browser.close();
console.log('font-fix shot done');
