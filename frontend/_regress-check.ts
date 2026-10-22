// 2026-10-22 小欧 - 重构后回归核对(临时): 真实文档 4 块的改动行数应与重构前一致
import { readFileSync } from 'node:fs';
import { normalizeMarkdownArt } from '@/components/markdown/asciiArt';

const DOC = 'F:/OmniAgentAs-repair/doc-开发规范/测试-线框.md';
const md = readFileSync(DOC, 'utf-8');
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
const art = blocks.filter((b) => /[┌┐└┘├┤┬┴┼─│╭╮╰╯═║]/.test(b));
const counts = art.map((b) => {
  const after = normalizeMarkdownArt('```\n' + b + '\n```')
    .replace(/^```\n?/, '')
    .replace(/\n?```$/, '');
  const bl = b.split('\n');
  const al = after.split('\n');
  return bl.filter((l, k) => l !== al[k]).length;
});
console.log('各块改动行数:', counts.join(','), '| 期望: 17,0,0,2');
console.log(
  counts.join(',') === '17,0,0,2' ? '✅ 与重构前完全一致' : '❌ 与重构前不一致'
);
