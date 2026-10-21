// ⚠ 工作副本(非正式代码): 2026-10-22 小欧 - 按三堂会审结论整改的候选实现。
//   测通后回填 asciiArt.ts, 本文件即删。
// 编辑历史:
// 2026-10-22 小欧 - 新建: Markdown 框线图(ASCII art)归一化器。
//   目的: LLM 现场手画的框线图必然"按字符数凑", 各行等宽性无保证; 且部分符号属
//   East-Asian Ambiguous 宽度(▲▼▶ 等 Consolas 无字形 → 回退 CJK 字体 → 2 倍宽),
//   渲染宽度随字体/语言环境跳变 → 页面上右边框参差。
//   本模块在**渲染期**做确定性重排: 把框线图当"弹性表格"布局, 列宽按内容实算,
//   输出每行严格等宽、竖线列全局对齐, 且**不改动任何正文文字**。
//   宽度模型: ASCII = 1 列(任何字体恒定); CJK/全角 = 2 列; 框线字符(─│┌┐└┘,
//   Consolas 内建)= 1 列; Ambiguous 箭头/三角(▲▼▶◀→←↑↓)= **降级为 ASCII** 后按 1 列。

/** 竖线/转角类字符(算作列锚点) */
const BORDER_CHARS = new Set([
  '|',
  '+',
  '│',
  '┃',
  '║',
  '┌',
  '┐',
  '└',
  '┘',
  '├',
  '┤',
  '┬',
  '┴',
  '┼',
  '╔',
  '╗',
  '╚',
  '╝',
  '╠',
  '╣',
  '╦',
  '╩',
  '╬',
  '╭',
  '╮',
  '╰',
  '╯',
  '┏',
  '┓',
  '┗',
  '┛',
]);

/** 横向填充字符(成串出现时视为"边线段") */
const RUN_CHARS = new Set(['-', '─', '━', '═']);

/**
 * Ambiguous 宽度符号 → ASCII 等价物(会审 P0-2: 根治宽度模型的不确定性)。
 * Consolas 无 ▲▼▶ 字形 → 浏览器回退 CJK 字体 → 实际渲染 2 倍宽, 与按 1 列计算不符。
 * 降级后恒为 1 列, 任何字体/语言环境下都成立。显示形态由 ▲▼▶ 变为 ^ v >。
 */
const GLYPH_FALLBACK: Readonly<Record<string, string>> = {
  '▲': '^',
  '▼': 'v',
  '▶': '>',
  '◀': '<',
  '►': '>',
  '◄': '<',
  '→': '>',
  '←': '<',
  '↑': '^',
  '↓': 'v',
  '⇒': '>',
  '⇐': '<',
  '⇑': '^',
  '⇓': 'v',
};

/** East-Asian Wide/Fullwidth 区段(2 列) */
const WIDE_RANGES: ReadonlyArray<[number, number]> = [
  [0x1100, 0x115f],
  [0x2e80, 0x303e],
  [0x3041, 0x33ff],
  [0x3400, 0x4dbf],
  [0x4e00, 0x9fff],
  [0xa000, 0xa4cf],
  [0xa960, 0xa97f],
  [0xac00, 0xd7a3],
  [0xf900, 0xfaff],
  [0xfe10, 0xfe19],
  [0xfe30, 0xfe6f],
  [0xff00, 0xff60],
  [0xffe0, 0xffe6],
  [0x1f300, 0x1f64f],
  [0x1f900, 0x1f9ff],
  [0x20000, 0x3fffd],
];

/** 单字符显示宽度: 全角 2 列, 其余 1 列 */
export function charWidth(ch: string): number {
  const cp = ch.codePointAt(0);
  if (cp === undefined) return 0;
  for (const [lo, hi] of WIDE_RANGES) {
    if (cp >= lo && cp <= hi) return 2;
  }
  return 1;
}

/** 字符串显示宽度 */
export function displayWidth(s: string): number {
  let w = 0;
  for (const ch of s) w += charWidth(ch);
  return w;
}

type Tok =
  | { kind: 'border'; ch: string; col: number }
  | { kind: 'run'; ch: string; n: number; col: number }
  | { kind: 'text'; ch: string; w: number; col: number };

interface ParsedLine {
  toks: Tok[];
  /** toks 中 border 的下标(升序) */
  borders: number[];
}

/** 把一行拆成 竖线锚点 / 横向边线段 / 正文 三类 token(箭头/三角先降级为 ASCII) */
function tokenize(line: string): ParsedLine {
  const toks: Tok[] = [];
  const borders: number[] = [];
  let col = 0;
  let i = 0;
  while (i < line.length) {
    const raw = line[i] as string;
    const ch = GLYPH_FALLBACK[raw] ?? raw;
    if (BORDER_CHARS.has(ch)) {
      borders.push(toks.length);
      toks.push({ kind: 'border', ch, col });
      col += 1;
      i += 1;
    } else if (RUN_CHARS.has(ch)) {
      let n = 0;
      while (i < line.length) {
        const c2 = GLYPH_FALLBACK[line[i] as string] ?? (line[i] as string);
        if (!RUN_CHARS.has(c2)) break;
        n += 1;
        i += 1;
      }
      toks.push({ kind: 'run', ch, n, col });
      col += n;
    } else {
      const w = charWidth(ch);
      toks.push({ kind: 'text', ch, w, col });
      col += w;
      i += 1;
    }
  }
  return { toks, borders };
}

/** 该行是否为"纯边线行"(只含竖线/横线/空格) */
function isFrameRow(line: string): boolean {
  const t = line.trim();
  if (t.length === 0) return false;
  let hasBorder = false;
  for (const raw of t) {
    const ch = GLYPH_FALLBACK[raw] ?? raw;
    if (BORDER_CHARS.has(ch)) {
      hasBorder = true;
    } else if (!RUN_CHARS.has(ch) && ch !== ' ') {
      return false;
    }
  }
  return hasBorder;
}

/** 该行是否含 ≥2 个竖线锚点 */
function borderCount(line: string): number {
  let n = 0;
  for (const raw of line) {
    const ch = GLYPH_FALLBACK[raw] ?? raw;
    if (BORDER_CHARS.has(ch)) n += 1;
  }
  return n;
}

/** 该行是否含横向边线段(≥2 连) */
function hasRun(line: string): boolean {
  let run = 0;
  for (const raw of line) {
    const ch = GLYPH_FALLBACK[raw] ?? raw;
    if (RUN_CHARS.has(ch)) {
      run += 1;
      if (run >= 2) return true;
    } else {
      run = 0;
    }
  }
  return false;
}

/**
 * 是否是"框线图"代码块 —— 三重判据, 避免误伤普通代码/表格。
 * ① ≥3 非空行; ② ≥2 行"纯边线行"(图的上下边框; Markdown 表格分隔行只有 1 行 → 不触发);
 * ③ ≥60% 的行含 ≥2 个竖线锚点, 且至少含 1 段横向边线。
 */
export function looksLikeArt(lines: string[]): boolean {
  const nonEmpty = lines.filter((l) => l.trim().length > 0);
  if (nonEmpty.length < 3) return false;
  const frameRows = lines.filter(isFrameRow).length;
  if (frameRows < 2) return false;
  const withBorders = nonEmpty.filter((l) => borderCount(l) >= 2).length;
  if (withBorders < 2) return false;
  if (!nonEmpty.some(hasRun)) return false;
  return withBorders / nonEmpty.length >= 0.6;
}

/** 取出该行的"正文文字"(去掉竖线/横线/空白), 用于重排后的内容守恒校验 */
function wordsOf(line: string): string {
  let out = '';
  for (const raw of line) {
    const ch = GLYPH_FALLBACK[raw] ?? raw;
    if (BORDER_CHARS.has(ch) || RUN_CHARS.has(ch) || ch === ' ') continue;
    out += ch;
  }
  return out;
}

/**
 * 若干列值按容差聚类, 返回每簇的代表列(取簇内最大值)。
 * 链式判定(与"距簇首"相比): 新值与**簇尾**相差 ≤ tol 即并入当前簇。
 *   原因: 同一根竖线在不同行可能相差 1~2 列(如"长文本行"把框右边框顶出去 1 列),
 *   "距簇首"判定会因簇首已占位而把它们劈成两簇 → 同一个框的竖线列不一致 → 还是歪的。
 */
function clusterCols(cols: number[], tol: number): number[] {
  if (cols.length === 0) return [];
  const sorted = [...cols].sort((a, b) => a - b);
  const out: number[] = [];
  let start = sorted[0] as number;
  let max = start;
  for (let i = 1; i < sorted.length; i += 1) {
    const v = sorted[i] as number;
    if (v - max <= tol) {
      if (v > max) max = v;
    } else {
      out.push(max);
      start = v;
      max = v;
    }
  }
  out.push(max);
  return out;
}

/** 段内内容: 去掉首尾空白后的正文与其显示宽 */
function segmentContent(
  toks: Tok[],
  from: number,
  to: number
): { text: string; width: number; isRun: boolean; authored: number } {
  let text = '';
  let width = 0;
  let authored = 0;
  let isRun = false;
  let hasText = false;
  for (let i = from; i < to; i += 1) {
    const t = toks[i] as Tok;
    if (t.kind === 'run') {
      isRun = true;
      text += t.ch.repeat(t.n);
      width += t.n;
      authored += t.n;
    } else if (t.kind === 'text') {
      hasText = true;
      text += t.ch;
      width += t.w;
      authored += t.w;
    }
  }
  // 只有"整段全是横线"才算边线段; 段内夹了正文(如 "Short-term / Long-term" 或 "──▶")
  // 里的连字符不算边线, 否则会把正文当边线铺满整格
  if (isRun && !hasText) {
    return { text, width, isRun: true, authored };
  }
  const trimmed = text.replace(/^\s+/, '').replace(/\s+$/, '');
  return { text: trimmed, width: displayWidth(trimmed), isRun: false, authored };
}

/**
 * 重排框线图: 每行严格等宽, 竖线列全局对齐。
 * 返回 null 表示"不该重排"(非框线图, 或重排会改动正文文字) —— 调用方保留原文。
 */
export function reflowArt(lines: string[]): string[] | null {
  if (!looksLikeArt(lines)) return null;

  const parsed = lines.map(tokenize);

  // ① 列锚点: 每行第一个竖线 → 全局最左列; 最后一个竖线 → 全局最右列; 中间竖线 → 聚类
  let gMin = Number.POSITIVE_INFINITY;
  let gMax = Number.NEGATIVE_INFINITY;
  const interiorCols: number[] = [];
  for (const p of parsed) {
    if (p.borders.length === 0) continue;
    const first = p.toks[p.borders[0] as number] as Tok;
    const last = p.toks[p.borders[p.borders.length - 1] as number] as Tok;
    gMin = Math.min(gMin, first.col);
    gMax = Math.max(gMax, last.col);
    for (let k = 1; k < p.borders.length - 1; k += 1) {
      interiorCols.push((p.toks[p.borders[k] as number] as Tok).col);
    }
  }
  if (!Number.isFinite(gMin) || !Number.isFinite(gMax)) return null;

  const clusters = clusterCols(interiorCols, 1).filter(
    (c) => c > gMin && c < gMax
  );

  // 每个竖线的目标列(第一根→最左列, 最后一根→最右列, 中间→聚类)
  const rawTarget: number[][] = parsed.map((p) =>
    p.borders.map((ti, k) => {
      const t = p.toks[ti] as Tok;
      if (k === 0) return gMin;
      if (k === p.borders.length - 1) return gMax;
      let best = t.col;
      let bestD = Number.POSITIVE_INFINITY;
      for (const c of clusters) {
        const d = Math.abs(c - t.col);
        if (d < bestD) {
          bestD = d;
          best = c;
        }
      }
      return bestD <= 1 ? best : t.col;
    })
  );

  // 阶段2(会审 P0-3): 落单竖线吸附。
  //   症状: 某行的长文字把竖线顶到别处(如记忆框右边框: 上/下边线行在第 35 列,
  //   文字行被顶到第 36 列) → 同一个框的竖线列不一致 → 框线还是歪的。
  //   规则: 与"有簇支撑"的列距离 ≤ 左侧格宽的 30% 时吸附过去(格窄说明两根竖线
  //   本来就是一对, 不能吸到同一列); 吸附后若同一行出现重复列 → 该行放弃吸附。
  const snappedTarget: number[][] = rawTarget.map((targets, li) => {
    const p = parsed[li] as ParsedLine;
    if (p.borders.length < 2) return targets;
    const out = [...targets];
    const snapped: number[] = [];
    for (let k = 1; k < p.borders.length - 1; k += 1) {
      const t = p.toks[p.borders[k] as number] as Tok;
      if (targets[k] !== t.col) continue; // 已有簇归属, 不动
      const prev = p.toks[p.borders[k - 1] as number] as Tok;
      const leftCell = t.col - prev.col - 1;
      let best = -1;
      let bestD = Number.POSITIVE_INFINITY;
      for (const c of clusters) {
        const d = Math.abs(c - t.col);
        if (d < bestD) {
          bestD = d;
          best = c;
        }
      }
      if (best < 0) continue;
      const allow = Math.max(1, Math.floor(leftCell * 0.3));
      if (bestD <= allow) {
        out[k] = best;
        snapped.push(k);
      }
    }
    // 吸附后同一行出现重复列 → 放弃本行全部吸附(宁可保持原样, 不塌框)
    const seen = new Set<number>();
    for (let k = 0; k < out.length; k += 1) {
      if (seen.has(out[k] as number)) {
        for (const sk of snapped) out[sk] = (rawTarget[li] as number[])[sk] as number;
        break;
      }
      seen.add(out[k] as number);
    }
    return out;
  });

  // 阶段3(会审 P0-4): 同行重复列回退 —— 聚类/吸附可能让同一行的两根竖线落到同一列
  //   (窄框的两条边只差 1~2 列, 会被并簇) → 框会塌成 0 宽。检出即回退为各自原列。
  const targetOf: number[][] = snappedTarget.map((targets, li) => {
    const p = parsed[li] as ParsedLine;
    const out = [...targets];
    const count = new Map<number, number>();
    for (const t of out) count.set(t, (count.get(t) ?? 0) + 1);
    for (let k = 1; k + 1 < out.length; k += 1) {
      const t = out[k] as number;
      if ((count.get(t) ?? 0) > 1) {
        const own = (p.toks[p.borders[k] as number] as Tok).col;
        out[k] = own;
        count.set(t, (count.get(t) as number) - 1);
        count.set(own, (count.get(own) ?? 0) + 1);
      }
    }
    return out;
  });

  // ② 全局列序列
  const canonSet = new Set<number>([gMin, gMax]);
  for (const arr of targetOf) for (const c of arr) canonSet.add(c);
  const canon = [...canonSet].sort((a, b) => a - b);
  const canonIdxOf = new Map<number, number>();
  canon.forEach((c, i) => canonIdxOf.set(c, i));

  // ③ 弹性列宽: 相邻两列之间, 取所有行"该段内容实需宽度"的最大值
  const gap = new Array<number>(canon.length - 1).fill(0);
  const spans: Array<{ a: number; b: number; need: number }> = [];
  for (let li = 0; li < parsed.length; li += 1) {
    const p = parsed[li] as ParsedLine;
    const targets = targetOf[li] as number[];
    for (let k = 0; k + 1 < p.borders.length; k += 1) {
      const bi = p.borders[k] as number;
      const bj = p.borders[k + 1] as number;
      const ia = canonIdxOf.get(targets[k] as number) as number;
      const ib = canonIdxOf.get(targets[k + 1] as number) as number;
      const seg = segmentContent(p.toks, bi + 1, bj);
      // 纯横线段按"实占宽度"计(它就是那条边线); 含正文的段额外留 1 列呼吸位
      const need = seg.isRun ? seg.width : seg.width + 2;
      const base = Math.max(seg.authored, need);
      if (ib === ia + 1) {
        gap[ia] = Math.max(gap[ia] as number, base);
      } else {
        spans.push({ a: ia, b: ib, need: base });
      }
    }
  }

  // ④ 跨列行(内容横跨多列)内容过长时, 把亏空摊到跨过的列上
  for (const sp of spans) {
    let total = 0;
    for (let i = sp.a; i < sp.b; i += 1) total += (gap[i] as number) + 1;
    const deficit = sp.need - (total - 1);
    if (deficit > 0) {
      const cnt = sp.b - sp.a;
      const add = Math.ceil(deficit / cnt);
      for (let i = sp.a; i < sp.b; i += 1) gap[i] = (gap[i] as number) + add;
    }
  }

  // ⑤ 列位置
  const pos: number[] = [gMin];
  for (let i = 0; i + 1 < canon.length; i += 1) {
    pos.push((pos[i] as number) + 1 + (gap[i] as number));
  }

  // ⑥ 逐行输出
  const out: string[] = [];
  for (let li = 0; li < parsed.length; li += 1) {
    const p = parsed[li] as ParsedLine;
    const targets = targetOf[li] as number[];
    if (p.borders.length === 0) {
      out.push(lines[li] as string);
      continue;
    }
    let buf = '';
    let cur = 0;
    const emitPad = (to: number) => {
      const n = to - cur;
      if (n > 0) {
        buf += ' '.repeat(n);
        cur = to;
      }
    };
    // 首竖线之前的内容(通常为空)
    const lead = segmentContent(p.toks, 0, p.borders[0] as number);
    buf += lead.text;
    cur = displayWidth(lead.text);
    for (let k = 0; k < p.borders.length; k += 1) {
      const bi = p.borders[k] as number;
      const bt = p.toks[bi] as Tok;
      const target = pos[canonIdxOf.get(targets[k] as number) as number] as number;
      emitPad(Math.max(target, cur));
      buf += bt.ch;
      cur = Math.max(target, cur) + 1;
      // 与下一竖线之间的内容
      if (k + 1 < p.borders.length) {
        const bj = p.borders[k + 1] as number;
        const nextTarget =
          pos[canonIdxOf.get(targets[k + 1] as number) as number] as number;
        const seg = segmentContent(p.toks, bi + 1, bj);
        const region = Math.max(nextTarget - cur, 0);
        if (seg.isRun) {
          // 边线段: 铺满整段, 保证同一列在所有行都占同样宽度
          const fill = Math.max(region, 1);
          buf += (seg.text[0] ?? '-').repeat(fill);
          cur += fill;
        } else if (seg.text.length === 0) {
          // 空段: 留白, 不推进游标(下一根竖线按 canonical 列落位)
          emitPad(cur);
        } else {
          const left = Math.floor(Math.max(region - seg.width, 0) / 2);
          emitPad(cur + left);
          buf += seg.text;
          cur += seg.width;
        }
      }
    }
    // 末竖线之后的内容(通常为空)
    const tail = segmentContent(
      p.toks,
      (p.borders[p.borders.length - 1] as number) + 1,
      p.toks.length
    );
    buf += tail.text;
    out.push(buf);
  }

  // ⑦ 内容守恒校验: 逐行的"正文文字"必须与原文完全一致(只允许挪动空格与横线)
  for (let i = 0; i < out.length; i += 1) {
    if (wordsOf(out[i] as string) !== wordsOf(lines[i] as string)) return null;
  }

  // ⑧ 等宽校验: 不等宽则补齐到同一宽度; 补不齐说明算法有漏, 宁可不改
  const widths = out.map((l) => displayWidth(l));
  const max = Math.max(...widths);
  const padded = out.map((l, i) => l + ' '.repeat(max - (widths[i] as number)));
  const w2 = new Set(padded.map((l) => displayWidth(l)));
  if (w2.size > 1) return null;
  return padded;
}

/**
 * 归一化整篇 Markdown 中的围栏代码块(框线图)。
 * 只处理 ``` 围栏块内部, 且仅当该块判定为框线图时重排; 其余内容逐字保留。
 */
export function normalizeMarkdownArt(markdown: string): string {
  if (!markdown) return markdown;
  // 快速否决: 没有围栏 / 没有任何框线字符 → 不可能是框线图, 直接返回(流式性能)
  if (!markdown.includes('```') && !markdown.includes('~~~')) return markdown;
  if (!/[│|─━═┌┐└┘├┤┬┴┼]/.test(markdown)) return markdown;

  // CRLF 归一: '\r' 会被当成正文, 导致守恒校验必然不等 → 整块放弃重排
  const hadCRLF = markdown.includes('\r\n');
  const src = hadCRLF ? markdown.replace(/\r\n/g, '\n') : markdown;

  const lines = src.split('\n');
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const m = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[i] as string);
    if (!m) {
      out.push(lines[i] as string);
      i += 1;
      continue;
    }
    const fence = m[1] as string;
    const info = (m[2] as string).trim();
    const closeRe = new RegExp(
      `^ {0,3}${fence[0] === '`' ? '`' : '~'}{${fence.length},}\\s*$`
    );
    let closeAt = -1;
    for (let k = i + 1; k < lines.length; k += 1) {
      if (closeRe.test(lines[k] as string)) {
        closeAt = k;
        break;
      }
    }
    if (closeAt < 0) {
      out.push(lines[i] as string);
      i += 1;
      continue;
    }
    const body = lines.slice(i + 1, closeAt);
    out.push(lines[i] as string);
    if (info.toLowerCase() === 'mermaid') {
      out.push(...body);
    } else {
      const reflowed = reflowArt(body);
      out.push(...(reflowed ?? body));
    }
    out.push(lines[closeAt] as string);
    i = closeAt + 1;
  }
  const result = out.join('\n');
  return hadCRLF ? result.replace(/\n/g, '\r\n') : result;
}

export default normalizeMarkdownArt;
