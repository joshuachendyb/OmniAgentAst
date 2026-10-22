// 2026-10-22 小欧 - 回归核对(临时): ① REAL 样本对齐是否仍成立 ② 真实文档各块差异行归因
import { readFileSync } from 'node:fs';
import { reflowArt, charWidth, displayWidth } from '@/components/markdown/asciiArt';

const SAMPLE = [
  '\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510',
  '\u2502                 Agent System                 \u2502',
  '\u2502                                              \u2502',
  '\u2502   \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510    \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510   \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510 \u2502',
  '\u2502   \u2502 \u611F\u77E5        \u2502\u2500\u2500\u2500\u25B6\u2502 \u89C4\u5212     \u2502\u2500\u25B6\u2502 \u884C\u52A8   \u2502 \u2502',
  '\u2502   \u2502 Perception  \u2502    \u2502 Planning \u2502   \u2502 Action \u2502 \u2502',
  '\u2502   \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518    \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518   \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2502',
  '\u2502        \u25B2                                    \u2502',
  '\u2502        \u2502             \u25BC                      \u2502',
  '\u2502   \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510          \u2502',
  '\u2502   \u2502 \u8BB0\u5FC6                         \u2502          \u2502',
  '\u2502   \u2502 Short-term / Long-term / Trace\u2502          \u2502',
  '\u2502   \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518          \u2502',
  '\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518',
];

console.log('=== ① REAL 样本归一后各行边框列 ===');
const out = reflowArt(SAMPLE);
out.forEach((l, i) => {
  const marks: string[] = [];
  let col = 0;
  for (const ch of l) {
    if ('\u2502\u2510\u2518\u2524\u2551'.includes(ch)) marks.push(ch + '@' + col);
    col += charWidth(ch);
  }
  console.log(String(i).padStart(2), 'w=' + String(displayWidth(l)).padStart(3), '|', marks.join(' '));
});

console.log('\n=== ② 真实文档 4 块: 差异行数 + 接头字符保留核对 ===');
const md = readFileSync(
  'F:/OmniAgentAs-repair/doc-开发规范/测试-线框.md',
  'utf-8'
);
const blocks: string[] = [];
const lines = md.split(/\r?\n/);
let inFence = false;
let cur: string[] = [];
for (const l of lines) {
  if (/^\s{0,3}(```|~~~)/.test(l)) {
    if (!inFence) {
      inFence = true;
      cur = [];
    } else {
      inFence = false;
      blocks.push(cur.join('\n'));
    }
    continue;
  }
  if (inFence) cur.push(l);
}
const art = blocks.filter((b) => /[\u250C\u2510\u2514\u2518\u251C\u2524\u252C\u2534\u253C\u2500\u2502\u256D\u256E\u2570\u256F\u2550\u2551]/.test(b));
art.forEach((b, i) => {
  const after = reflowArt(b);
  const bl = b.split('\n');
  const al = after.split('\n');
  const changed = bl.filter((l, k) => l !== al[k]).length;
  // 接头字符(┬┴┼)数量守恒?
  const j = (s: string) => (s.match(/[\u252C\u2534\u253C]/g) ?? []).length;
  const jBefore = bl.reduce((a, l) => a + j(l), 0);
  const jAfter = al.reduce((a, l) => a + j(l), 0);
  console.log(
    `块${i + 1}: 行数 ${bl.length}→${al.length}, 改动行 ${changed}, 接头字符 ${jBefore}→${jAfter} ${jBefore === jAfter ? '✅守恒' : '❌丢失'}`
  );
});
