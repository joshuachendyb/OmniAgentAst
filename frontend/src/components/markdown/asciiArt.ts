// 【模块】Markdown 框线图(ASCII art)对齐器 —— 显示列空间 · 按框局部对齐
//
// 【为什么重写】前一版(自制"全局列聚类 + 弹性表格 + 吸附回退", 450 行)属过度设计:
//   把整张图当一张表做全局列对齐 → 跨框串扰、且会把内容重新居中(改作者原意)。
//   行业既有实现一致采用**按框局部对齐**:
//     · ascii-chart-formatter (MIT, MichaelTien8901/ascii-chart-formatter)
//         "Fixes misaligned right edges in ASCII-art box diagrams caused by LLM character counting errors"
//     · ascii-box-aligner (PyPI 0.1.0)   同族: 嵌套树 + 后序(先内后外)
//     · CPIDLE/ascii-tools ascii-align     同族: 宽度表 + 符号处理
//   本文件 = 该算法移植到 TS, 并做四处针对性改良(见下)。
//
// 【算法】(每框独立, 不做全局列)
//   1) 找"边线段": 角字符 + 横线填充(+T 型接头) + 角字符 → 一行可有多个(并排框)
//   2) 配对成框: 上下边线 (左列, 宽) 相同; 堆叠框允许"上一框下边线 = 下一框上边线",
//      但须下一行同列有竖线(证明是内容行, 不是箭头/空行)
//   3) 加宽: 框内内容显示宽 > 框宽 → 上下边线补填充字符(不压内容)
//   4) 对齐内容行: 左边线(按显示列就近) → 右边线(按显示列就近, 且不得越过下一框左边界)
//      → 只把框内内容按显示宽"补空格/裁尾空格"到框内宽(不动内容本身)
//   5) 顺序: 先内层后外层, 同层从左到右; 加宽后重新识别, 最多 4 轮
//
// 【与上游的差异】(均为针对性改良)
//   a) 宽度用 get-east-asian-width(Unicode EAW) 替代上游手写表; Ambiguous 按 2 列
//      (框线块 U+2500–259F 与 Latin-1 U+00A0–00FF 例外为 1 列, 见【宽度模型 vs 实渲染】)。
//   b) **框几何全部在"显示列"空间**(上游用字符索引): CJK 内容把框线顶偏是**显示列**问题,
//      按字符数补/裁空格会把整个框右移(上游在"一行多框 + CJK"下会错位)。
//   c) 本框右边线**不得越过同行下一框的左边线**(上游没这条硬约束 → 切片会吞掉下一框内容)。
//   d) **不改作者的符号**: 框线/箭头/三角一律原样保留;
//      显示端的字宽保证由等宽字体栈提供(▶/几何符号按 2 列 → 栈首须为 Sarasa Mono SC, 见【宽度模型 vs 实渲染】)。
//   e) 只处理**围栏代码块内部**, 围栏外一律不碰。
//
// 【宽度模型 vs 实渲染】(2026-10-22 小欧 实测 Chromium canvas, 本机):
//   本模块的列宽模型以**栈首字体 Sarasa Mono SC** 为准(拉丁 0.5em = 1 格):
//     ASCII 1 格 / CJK·全角 2 格 / 框线·块元素 1 格 / 几何形状·箭头 2 格 / Latin-1 1 格。
//   各候选字体的实测字宽(÷拉丁 advance):
//     字体            ─      ▶      CJK     │墨迹   结论
//     Sarasa Mono SC 1.000  2.000  2.000   1.17em  ✅ 模型=实渲染, 边框像素级齐(栈首选)
//     Cascadia Mono 1.000  1.000  1.707   1.14em  ✗ CJK 非整数格 → 汉字框残差 ~0.29 格/字
//     Consolas      1.000  1.567  1.819   1.12em  ✗ 缺 ▶ 字形 + CJK 非整数格 → 残差更大
//   ⚠ 行高: │ 墨迹高 1.12–1.17em → 代码块行高须 ≤1.14 才连成实线(现取 1.1);
//     竖线"断成虚线"的根因是行高(12px 字继承 18px 行高 = 1.5), 与字体无关。
//
// 编辑历史:
// 2026-10-22 小欧 - 新建(工作副本): 按 ascii-chart-formatter / ascii-box-aligner 的
//   "按框局部对齐"算法重写框线图对齐器, 几何改在显示列空间。
// 2026-10-22 小欧 - 回填正式代码: 工作副本测通后回填本文件(唯一实现), 工作副本 asciiArt.work.ts 已删;
//   渲染层接入点 = MarkdownSlot.tsx 一行接入(两个渲染分支共用);
//   analyzeBoxes 由"调试用临时导出"改标注为**测试支撑导出**(单测断言框内右边线列一致性, 生产渲染路径不调用);
//   头部补【宽度模型 vs 实渲染】实测结论(字体栈必须保证 CJK 恰好 2 格) — 小欧-2026-10-22
// 2026-10-22 小欧 - 列宽模型改按 **Sarasa Mono SC 实测口径**:
//   East-Asian Ambiguous 由"1 格"改为"2 格", 仅框线块+块元素(U+2500–259F)与 Latin-1(U+00A0–00FF)例外;
//   实测 Sarasa: 框线 1 格 / 几何形状·箭头 2 格 / CJK 2 格 → 模型与实渲染完全一致, 边框像素级齐。
//   ⚠ 依赖 FontFamily.MONO 把 'Sarasa Mono SC' 放在栈首(见 utils/stepStyles.ts)。 — 小欧-2026-10-22
// 2026-10-22 小欧 - 修正 Ambiguous 宽度选项名: get-east-asian-width 1.7.0 的选项是
//   `ambiguousAsWide`(实现内默认 false = Ambiguous 按 1 列; 其 .d.ts 写的 "@default true" 与实现不符,
//   实测 ▲▼▶→ 默认即 1), 原写法 `ambiguousIsNarrow` 非合法选项(多余字段) → TS 报 TS2353 编译不过;
//   改为显式 `{ ambiguousAsWide: false }`, **运行时行为与原写法一致**(本就按 1 列)。 — 小欧-2026-10-22
// 2026-10-22 小欧 - **对齐核心换代**:
//   ① 锚点反转: 原以"边线行"为锚 → 刚性内容(Sarasa 下 ▶ 占 2 格)把内容行整体推右,
//      边线行没这些刚性字符 → 两行永远对不上(实测越修越歪)。现改为**边线行跟随内容行**:
//      L = 内容行左边线列的最右者, W = max(边线行宽, 内容行自然宽+2), 边线行按 L/R 重画。
//   ② 边界认领: 同行左到右逐个认领左边界(排除前框已认领的右边界)→ 不再把前框右边线
//      误当本框左边线(原为真 bug: 段宽算错 → 框被错误加宽)。
//   ③ 右边界取法: 取"右邻**兄弟**框左边界 - 1"之前的**最后一个**边界字符(嵌套框不参与 cap);
//      原"离期望最近者"会误取下一框的左边线。
//   ④ 边线行只调末尾纯填充字符, 段内接头字符(┬┴┼├┤)原位保留 → 不丢"分支点"语义。
//   ⑤ 误伤守卫收紧: 判据由"含任意框线字符"改为"含**框角**(或 ASCII 框线整行)"→
//      时序图(只有竖线+箭头)不再被当框图处理(实测原会挪动生命线)。
//   ⑥ 定位逻辑抽成 locateRowEdges, 主算法与测试支撑导出 analyzeBoxes 共用(同口径, DRY)。
//   实测: 真实文档《[1]系统架构全景解析…》58 行架构图 → 14 行全部对齐(外框 0→54,
//   内框 4→18 / 24→35 / 40→49, 记忆框 4→36); 时序图/树图 0 行改动。 — 小欧-2026-10-22
// 2026-10-22 小欧 - 更正上面「Ambiguous 宽度选项」那条历史并收敛热路径分配:
//   ① 上一条写的 `{ ambiguousAsWide: false }`(按 1 列)与实现不符 —— 实现取 `true`
//      (Ambiguous 按 2 列), 这才与 Sarasa Mono SC 实测(CJK/几何符号/箭头 2 格)一致;
//      本条为准, 上一条作废。
//   ② charWidth 逐字符新建选项对象 → 选项提为模块级常量(热路径零分配)。 — 小欧-2026-10-22
// 2026-10-22 小欧 - 框边定位三处修正:
//   ① 上下边线宽差容差 ≤1 列: 手绘图顶/底边线常差一横, 严格相等会把整框丢弃。
//   ② natural 一律裁尾空格: 末个框线字符之后的尾部空格是 padding 非结构间隙,
//      不裁会让内框变宽并把外框顶胖。
//   ③ 右边界改两相位认领: 相位①认领左边界时按"下一框目标左列-1"试探认领本框右边界
//      (防下一框把前框右边线误认作本框左边线); 相位②用精确 cap 重定位右边界,
//      认领集只含左边界, 避免试探认领污染精确定位。 — 小欧-2026-10-22

import { eastAsianWidth } from 'get-east-asian-width';

/** 角字符(框的转角/接头) */
const CORNER_CHARS = new Set('┌┐└┘├┤┬┴┼╔╗╚╝╠╣╦╩╬╭╮╰╯┏┓┗┛+'.split(''));

/** Unicode 框角(不含 ASCII 的 '+', 那条走"整行"判据) —— 由 CORNER_CHARS 派生, 单一真相源 */
const UNICODE_CORNER_RE = new RegExp(
  `[${[...CORNER_CHARS].filter((c) => c !== '+').join('')}]`
);

/** 横线填充字符 */
const HORIZONTAL_FILL_CHARS = new Set('─━═-┄┅┈┉');

/** 竖线字符 */
const VERTICAL_BORDER_CHARS = new Set('│║┃|┆┇┊┋');

/**
 * 单字符显示宽 —— **按 Sarasa Mono SC 的实测渲染口径**(拉丁 0.5em = 1 格)。
 * 2026-10-22 实测(Sarasa Mono SC, Chromium canvas, 拉丁宽 40px=20px 即 0.5em):
 *   ASCII 1 格 / CJK·全角 2 格 / 框线块(U+2500–257F) 1 格 / 块元素(U+2580–259F) 1 格 /
 *   几何形状(U+25A0–25FF) 2 格 / 箭头(U+2190–21FF) 2 格 / Latin-1(U+00A0–00FF) 实测 1 格。
 * 即: East-Asian Ambiguous 一律按 **2 格**, 仅两处例外按 1 格(框线+块元素 / Latin-1)。
 * ⚠ Latin-1 例外是**实测值**(该段字符在 Sarasa 里落到 1 格), 不是"EAW 窄"的推导结论 ——
 *   改动字体栈时必须重新实测本表, 否则框线会错位。
 * ⚠ 该口径以"字体栈首字体 Sarasa Mono SC"为准 —— 落到 Consolas/Cascadia 时 CJK(1.819/1.707 格)
 *   与几何符号(1 格)都和模型对不上, 边框会有残差(实测表见文件头);
 *   故 FontFamily.MONO 必须把 Sarasa Mono SC 放在**栈首**。
 * ⚠ 不用 string-width: 它带 emoji 规则, 会把 U+25B6(▶) 当 emoji 算 2 列, 与框线模型打架。
 * ⚠ get-east-asian-width 的选项名按 1.7.0 实 API 写 `{ ambiguousAsWide: true }`;
 *   写成 `ambiguousIsNarrow` 不是合法选项(多余字段) → TS 报 TS2353 编译不过。
 */
/**
 * EAW 选项: Ambiguous 按 2 列(与 Sarasa Mono SC 实测一致)。
 * 2026-10-22 小欧 - 提为模块级常量: 原先 charWidth 逐字符新建对象(热路径逐字符分配)。 — 小欧-2026-10-22
 */
const EAW_AMBIGUOUS_WIDE = { ambiguousAsWide: true };

export function charWidth(ch: string): number {
  const cp = ch.codePointAt(0);
  if (cp === undefined) return 0;
  // Sarasa 实测两例外: 框线块+块元素(U+2500–259F)、Latin-1(U+00A0–00FF)
  if (cp >= 0x2500 && cp <= 0x259f) return 1;
  if (cp >= 0x00a0 && cp <= 0x00ff) return 1;
  return eastAsianWidth(cp, EAW_AMBIGUOUS_WIDE);
}

/** 字符串显示宽 */
export function displayWidth(s: string): number {
  let w = 0;
  for (const ch of s) w += charWidth(ch);
  return w;
}

/** 制表符展开为 4 空格 */
function expandTabs(s: string, size = 4): string {
  if (!s.includes('\t')) return s;
  let out = '';
  for (const ch of s) {
    if (ch === '\t') {
      out += ' '.repeat(size - (out.length % size));
    } else {
      out += ch;
    }
  }
  return out;
}

/** 一行里每个字符索引对应的显示列(末位追加总宽) */
function displayCols(line: string): number[] {
  const cols: number[] = [];
  let col = 0;
  for (const ch of line) {
    cols.push(col);
    col += charWidth(ch);
  }
  cols.push(col);
  return cols;
}

interface BorderInfo {
  /** 行下标 */
  lineIndex: number;
  /** 左角字符索引 */
  leftIdx: number;
  /** 右角字符索引 */
  rightIdx: number;
  /** 左角的显示列 */
  leftCol: number;
  /** 右角的显示列 */
  rightCol: number;
  /** 边线段显示宽(含两角) */
  width: number;
}

interface BoxRegion {
  top: BorderInfo;
  bottom: BorderInfo;
}

/** 找出一行里的所有"边线段"(角 + 横线 + 角; 支持 T 型接头, 一行可多段=并排框) */
function findBorderSegments(line: string, lineIndex: number): BorderInfo[] {
  const segments: BorderInfo[] = [];
  const cols = displayCols(line);
  let i = 0;
  while (i < line.length) {
    if (!CORNER_CHARS.has(line[i] as string)) {
      i += 1;
      continue;
    }
    const leftIdx = i;
    let j = i + 1;
    while (j < line.length) {
      const ch = line[j] as string;
      if (HORIZONTAL_FILL_CHARS.has(ch)) {
        j += 1;
      } else if (CORNER_CHARS.has(ch)) {
        // T 型接头(后面紧跟填充)→ 继续; 否则是真右角 → 本段结束
        if (
          j + 1 < line.length &&
          HORIZONTAL_FILL_CHARS.has(line[j + 1] as string)
        ) {
          j += 1;
        } else {
          j += 1;
          break;
        }
      } else {
        break;
      }
    }
    const rightIdx = j - 1;
    if (rightIdx > leftIdx + 1 && CORNER_CHARS.has(line[rightIdx] as string)) {
      segments.push({
        lineIndex,
        leftIdx,
        rightIdx,
        leftCol: cols[leftIdx] as number,
        rightCol: cols[rightIdx] as number,
        width: (cols[rightIdx + 1] as number) - (cols[leftIdx] as number),
      });
      i = rightIdx; // 右角可能同时是下一个段的左角
    } else {
      i += 1;
    }
  }
  return segments;
}

function findBorders(lines: string[]): BorderInfo[] {
  const out: BorderInfo[] = [];
  lines.forEach((l, i) => out.push(...findBorderSegments(l, i)));
  return out;
}

/** 配对成框: 上下边线 左列相同 + 显示宽相同 */
function matchBoxes(borders: BorderInfo[], lines: string[]): BoxRegion[] {
  const usedAsTop = new Set<number>();
  const usedAsBottom = new Set<number>();
  const boxes: BoxRegion[] = [];
  const sorted = [...borders].sort(
    (a, b) => a.lineIndex - b.lineIndex || a.leftCol - b.leftCol
  );
  for (let i = 0; i < sorted.length; i += 1) {
    if (usedAsTop.has(i)) continue;
    const top = sorted[i] as BorderInfo;
    // 已作为下边线的边线, 只有"下一行同列有竖线"才可复用为上边线(堆叠框)
    if (usedAsBottom.has(i)) {
      const next = lines[top.lineIndex + 1];
      if (
        next === undefined ||
        top.leftIdx >= next.length ||
        !VERTICAL_BORDER_CHARS.has(next[top.leftIdx] as string)
      ) {
        continue;
      }
    }
    for (let j = i + 1; j < sorted.length; j += 1) {
      if (usedAsBottom.has(j)) continue;
      const bottom = sorted[j] as BorderInfo;
      // 2026-10-22 小欧 - 容忍上下框宽差 ≤1 列: 作者手绘图常见顶/底边线多画少画一横
      //   (真实文档《[1]系统架构全景解析》记忆框 top=36/bottom=37), 严格相等会把整框丢弃。
      if (
        bottom.leftCol === top.leftCol &&
        Math.abs(bottom.width - top.width) <= 1
      ) {
        boxes.push({ top, bottom });
        usedAsTop.add(i);
        usedAsBottom.add(j);
        break;
      }
    }
  }
  return boxes;
}

/** 把字符串补/裁到指定显示宽(只动尾随空格) */
function padOrTrimToWidth(s: string, target: number): string {
  const cur = displayWidth(s);
  if (cur < target) return s + ' '.repeat(target - cur);
  if (cur > target) {
    let out = s;
    let w = cur;
    while (w > target && out.endsWith(' ')) {
      out = out.slice(0, -1);
      w -= 1;
    }
    return out;
  }
  return s;
}

/** 一行里某框的左右边界定位结果 */
interface BoxEdge {
  /** 左边界字符下标(内容行=竖线, 边线行=角) */
  leftIdx: number;
  /** 右边界字符下标 */
  rightIdx: number;
  /** 左边界显示列 */
  leftCol: number;
  /** 右边界显示列 */
  rightCol: number;
  /** 段内正文自然宽(尾随空格已去; 结构段不裁) */
  natural: number;
}

/** 框的规范几何(显示列空间) */
interface BoxGeo {
  /** 规范左边界列 */
  L: number;
  /** 规范宽度(含左右边界) */
  W: number;
  /** 规范右边界列 = L + W - 1 */
  R: number;
}

/**
 * 在一行里找左边线: 按**显示列**就近(≤16 列)。
 * claimed = 同行**已被其它框认领**的边界列, 必须排除:
 *   内容行里前一个框的**右边线**常离本框规范左列更近(框被刚性内容推右时两者相邻),
 *   不排除就会把前框的右边线误当本框的左边线 → 段宽算错 → 框被错误加宽(实测越修越歪)。
 */
function findLeftBorder(
  line: string,
  cols: number[],
  targetCol: number,
  claimed: Set<number>
): number {
  let best = -1;
  let bestDist = Number.POSITIVE_INFINITY;
  for (let idx = 0; idx < line.length; idx += 1) {
    const col = cols[idx] as number;
    const dist = Math.abs(col - targetCol);
    if (dist > 16) continue;
    if (claimed.has(col)) continue;
    if (!VERTICAL_BORDER_CHARS.has(line[idx] as string)) continue;
    if (dist < bestDist) {
      bestDist = dist;
      best = idx;
      if (dist === 0) break;
    }
  }
  return best;
}

/**
 * 在一行里找右边线: 取 capCol 之前**最后一个**竖线(不是"离期望最近者")。
 * 理由: 一个框的右边线恒等于"下一个框的左边线之前的最后一条竖线";
 *   取"最近者"会在框被刚性内容推右时误取下一个框的左边线 → 把下一框的内容切进本框。
 */
function findRightBorder(
  line: string,
  cols: number[],
  from: number,
  capCol: number,
  claimed: Set<number>
): number {
  let right = -1;
  for (let idx = from + 1; idx < line.length; idx += 1) {
    const col = cols[idx] as number;
    if (col > capCol) break;
    if (claimed.has(col)) continue;
    if (!VERTICAL_BORDER_CHARS.has(line[idx] as string)) continue;
    right = idx;
  }
  return right;
}

/**
 * 在一行里找角字符(框的转角/接头): 取 capCol 之前**最后一个**角字符(同 findRightBorder 的理由)。
 */
function findCornerNear(
  line: string,
  cols: number[],
  from: number,
  capCol: number,
  claimed: Set<number>
): number {
  let best = -1;
  for (let idx = from; idx < line.length; idx += 1) {
    const col = cols[idx] as number;
    if (col > capCol) break;
    if (claimed.has(col)) continue;
    if (!CORNER_CHARS.has(line[idx] as string)) continue;
    best = idx;
  }
  return best;
}

/**
 * 定位某框在某行上的**左边界**字符下标(内容行=竖线, 边线行=角字符)。
 * 按显示列就近, 且不取同行已认领的列。
 */
function locateLeftEdge(
  line: string,
  cols: number[],
  frameRow: boolean,
  targetL: number,
  claimed: Set<number>
): number {
  return frameRow
    ? findLeftCorner(line, cols, targetL, claimed)
    : findLeftBorder(line, cols, targetL, claimed);
}

/**
 * 定位某框在某行上的**右边界**字符下标: 取 capCol 之前**最后一个**边界字符
 * (边线行=角字符, 内容行=竖线)。理由: 一个框的右边线恒等于"下一个框的左边线之前的
 * 最后一个边界字符"; 取"离期望最近者"会在框被刚性内容推右时误取下一框的左边线。
 */
function locateRightEdge(
  line: string,
  cols: number[],
  frameRow: boolean,
  fromIdx: number,
  capCol: number,
  claimed: Set<number>
): number {
  if (frameRow) {
    return findCornerNear(line, cols, fromIdx + 1, capCol, claimed);
  }
  return findRightBorder(line, cols, fromIdx, capCol, claimed);
}

/** 由左右边界下标算出该框在本行的段信息 */
function edgeOf(
  line: string,
  cols: number[],
  leftIdx: number,
  rightIdx: number
): BoxEdge {
  const inner = line.slice(leftIdx + 1, rightIdx);
  return {
    leftIdx,
    rightIdx,
    leftCol: cols[leftIdx] as number,
    rightCol: cols[rightIdx] as number,
    // 2026-10-22 小欧 - natural 一律裁尾: 末个框线字符之后的尾部空格是 padding
    //   不是结构间隙 → 不裁会把外层框顶宽(嵌套框变宽 → 外层框被顶胖)。
    //   刚性部分(框线/箭头/三角)都在末个框线字符之前, 裁尾不影响它们。
    natural: displayWidth(inner.replace(/\s+$/, '')),
  };
}

/** 在一行里找左边角(框的转角): 按显示列就近, 不取已认领列 */
function findLeftCorner(
  line: string,
  cols: number[],
  targetCol: number,
  claimed: Set<number>
): number {
  let best = -1;
  let bestDist = Number.POSITIVE_INFINITY;
  for (let idx = 0; idx < line.length; idx += 1) {
    if (!CORNER_CHARS.has(line[idx] as string)) continue;
    const col = cols[idx] as number;
    if (claimed.has(col)) continue;
    const dist = Math.abs(col - targetCol);
    if (dist > 16) continue;
    if (dist < bestDist) {
      bestDist = dist;
      best = idx;
      if (dist === 0) break;
    }
  }
  return best;
}

/**
 * 逐行定位各框的左右边界(**两阶段**, 主算法与测试支撑导出共用, 保证同口径):
 *   ① 同行左到右逐个认领**左边界**(就近 + 未被认领; 边线行找角字符, 内容行找竖线);
 *   ② 逐框取**右边界**: 上限 = 同行**兄弟框**(不含嵌套框)中右邻框的左边界 - 1,
 *      取该上限之前**最后一个**边界字符。
 *   ⚠ 认领是必须的: 不排除前一个框已认领的右边界, 会把前框的右边线当成本框的左边线。
 */
function locateRowEdges(
  line: string,
  rowIndex: number,
  rowBoxes: BoxRegion[],
  targetLOf: (box: BoxRegion) => number
): Map<BoxRegion, BoxEdge> {
  const cols = displayCols(line);
  const claimedP1 = new Set<number>();
  const claimedP2 = new Set<number>();
  const sorted = [...rowBoxes].sort((a, b) => a.top.leftCol - b.top.leftCol);
  const leftIdxOf = new Map<BoxRegion, number>();
  // 相位①: 认领左边界; 同时按"下一框目标左列-1"试探认领本框右边界,
  //   防止下一框把前框右边线误当成本框左边线(内容行被刚性内容推右时两者常相邻)。
  //   ⚠ 试探右只进 claimedP1(供相位①左搜索排除); 相位②右搜索用只含左界的 claimedP2,
  //   否则各框会把自己的试探右当成已占用 → 右边界找不到 → 整框被跳过。
  for (let i = 0; i < sorted.length; i += 1) {
    const box = sorted[i] as BoxRegion;
    const frameRow = isFrameRowOf(box, rowIndex);
    const idx = locateLeftEdge(line, cols, frameRow, targetLOf(box), claimedP1);
    if (idx < 0) continue;
    claimedP1.add(cols[idx] as number);
    claimedP2.add(cols[idx] as number);
    leftIdxOf.set(box, idx);
    const next = sorted[i + 1];
    const provCap = next ? targetLOf(next) - 1 : Number.POSITIVE_INFINITY;
    const rIdx = locateRightEdge(line, cols, frameRow, idx, provCap, claimedP1);
    if (rIdx > idx) claimedP1.add(cols[rIdx] as number);
  }
  // 相位②: 用精确 cap 重定位右边界(认领集只含左边界, 试探认领不污染精确定位)。
  const result = new Map<BoxRegion, BoxEdge>();
  for (let i = 0; i < sorted.length; i += 1) {
    const box = sorted[i] as BoxRegion;
    const leftIdx = leftIdxOf.get(box);
    if (leftIdx === undefined) continue;
    const boxL = cols[leftIdx] as number;
    let cap = Number.POSITIVE_INFINITY;
    for (const other of sorted) {
      if (other === box) continue;
      const otherIdx = leftIdxOf.get(other);
      if (otherIdx === undefined) continue;
      const otherL = cols[otherIdx] as number;
      if (otherL <= boxL) continue; // 只管右边的
      // 嵌套在本框内的框不参与 cap: 否则外框的 cap 会被内框顶掉,
      // 导致外框找不到自己的右边线(外框的右边线在最右, 不受内框约束)
      if (isNestedIn(box, other)) continue;
      cap = Math.min(cap, otherL - 1);
    }
    const frameRow = isFrameRowOf(box, rowIndex);
    const rightIdx = locateRightEdge(
      line,
      cols,
      frameRow,
      leftIdx,
      cap,
      claimedP2
    );
    if (rightIdx < 0 || rightIdx <= leftIdx) continue;
    claimedP2.add(cols[rightIdx] as number);
    result.set(box, edgeOf(line, cols, leftIdx, rightIdx));
  }
  return result;
}

/**
 * 重排一组行(一个围栏块或一个图区) —— 按框局部对齐。
 *
 * 【规范几何】(显示列空间)
 *   L = 该框**内容行**左边线列的最右者; W = max(边线行宽度, 内容行正文自然宽 + 2);
 *   R = L + W - 1。
 *   ⚠ 为什么 L 取内容行而不是边线行: 刚性内容(如 Sarasa 下占 2 格的 ▶)会把内容行整体推右,
 *     而边线行里没有这些刚性字符 → 两行对不上。若以边线行为锚, 框必然错位(实测越修越歪);
 *     故改为**边线行跟随内容行**: 边线行的角字符按 L/R 重画, 框间空隙用空格吸收差额。
 *   ⚠ 边线行的角列**不参与** L 的取最大(否则边线行右移 → 反馈回 L → 逐轮右漂)。
 */
function fixLines(lines: string[]): string[] {
  const out = lines.map((l) => expandTabs(l));
  const geoCache = new Map<string, BoxGeo>();
  for (let iteration = 0; iteration < 6; iteration += 1) {
    const borders = findBorders(out);
    const boxes = matchBoxes(borders, out);
    if (boxes.length === 0) return out;

    // 框的身份键: 上下边线行号 + 同组内序号(同一对边线行可能有多个并列框, 必须区分)
    const keys = new Map<BoxRegion, string>();
    {
      const groups = new Map<string, BoxRegion[]>();
      for (const box of boxes) {
        const k = `${box.top.lineIndex}:${box.bottom.lineIndex}`;
        const arr = groups.get(k) ?? [];
        arr.push(box);
        groups.set(k, arr);
      }
      for (const [k, arr] of groups) {
        arr.sort((a, b) => a.top.leftCol - b.top.leftCol);
        arr.forEach((b, i) => keys.set(b, `${k}#${i}`));
      }
    }
    const keyOf = (box: BoxRegion): string => keys.get(box) ?? '';

    // ① 逐行定位各框边界(同行左到右, 逐个认领边界列)
    const edges = new Map<BoxRegion, Map<number, BoxEdge>>();
    for (const box of boxes) edges.set(box, new Map());
    const rowBoxes = new Map<number, BoxRegion[]>();
    for (const box of boxes) {
      for (let r = box.top.lineIndex; r <= box.bottom.lineIndex; r += 1) {
        const arr = rowBoxes.get(r) ?? [];
        arr.push(box);
        rowBoxes.set(r, arr);
      }
    }
    for (const [rowIndex, arr] of rowBoxes) {
      const line = out[rowIndex] as string;
      const rowEdges = locateRowEdges(line, rowIndex, arr, (box) => {
        const geo = geoCache.get(keyOf(box));
        return geo ? geo.L : box.top.leftCol;
      });
      for (const [box, edge] of rowEdges) {
        (edges.get(box) as Map<number, BoxEdge>).set(rowIndex, edge);
      }
    }

    // ② 逐框算规范几何(左边界只增不减, 保证单调收敛)
    for (const box of boxes) {
      const perRow = edges.get(box) as Map<number, BoxEdge>;
      if (perRow.size === 0) continue;
      const contentEdges: BoxEdge[] = [];
      let frameWidth = 0;
      for (const [rowIndex, e] of perRow) {
        if (
          rowIndex === box.top.lineIndex ||
          rowIndex === box.bottom.lineIndex
        ) {
          frameWidth = Math.max(frameWidth, e.natural + 2);
        } else {
          contentEdges.push(e);
        }
      }
      let L = contentEdges.length > 0 ? -1 : box.top.leftCol;
      let W = frameWidth;
      for (const e of contentEdges) {
        if (e.leftCol > L) L = e.leftCol;
        const w = e.natural + 2;
        if (w > W) W = w;
      }
      if (L < 0) L = box.top.leftCol;
      if (W < 3) W = 3;
      const prev = geoCache.get(keyOf(box));
      const mergedL = prev ? Math.max(L, prev.L) : L;
      const mergedW = prev ? Math.max(W, prev.W) : W;
      geoCache.set(keyOf(box), {
        L: mergedL,
        W: mergedW,
        R: mergedL + mergedW - 1,
      });
    }

    // ③ 逐行重写到规范几何(先边线行角色 → 再内容行角色; 同行左到右)
    let changed = false;
    for (const rowIndex of [...rowBoxes.keys()].sort((a, b) => a - b)) {
      const arr = rowBoxes.get(rowIndex) as BoxRegion[];
      const frameBoxes = arr
        .filter(
          (b) => b.top.lineIndex === rowIndex || b.bottom.lineIndex === rowIndex
        )
        .sort((a, b) => a.top.leftCol - b.top.leftCol);
      const contentBoxes = arr
        .filter(
          (b) => b.top.lineIndex < rowIndex && rowIndex < b.bottom.lineIndex
        )
        .sort((a, b) => a.top.leftCol - b.top.leftCol);
      for (const box of [...frameBoxes, ...contentBoxes]) {
        const geo = geoCache.get(keyOf(box));
        if (!geo) continue;
        const before = out[rowIndex] as string;
        const after = rewriteRow(before, box, rowIndex, geo, {
          keyOf,
          geoCache,
          rowBoxList: arr,
        });
        if (after !== before) {
          out[rowIndex] = after;
          changed = true;
        }
      }
    }
    if (!changed) return out;
  }
  return out;
}

/** 该行对某框而言是边线行还是内容行 */
function isFrameRowOf(box: BoxRegion, rowIndex: number): boolean {
  return rowIndex === box.top.lineIndex || rowIndex === box.bottom.lineIndex;
}

/** other 是否嵌套在 box 之内(按边线行的左右角列判定) */
function isNestedIn(box: BoxRegion, other: BoxRegion): boolean {
  return (
    box.top.leftCol <= other.top.leftCol &&
    other.top.rightCol <= box.top.rightCol
  );
}

/**
 * 重写阶段所需的上下文(规范几何查表 + 同行框清单 + 框身份键映射)。
 * 收成对象传参: rewriteRow 原为 7 个参数(位置参数超过 5 个已难读, SLAP)。
 */
interface RewriteCtx {
  /** 框身份键(跨轮次稳定) */
  keyOf: (box: BoxRegion) => string;
  /** 框的规范几何(按身份键索引) */
  geoCache: Map<string, BoxGeo>;
  /** 同行相关的框 */
  rowBoxList: BoxRegion[];
}

/**
 * 把某框在某一行上的片段重写到规范几何。
 * 边线行: 角字符落在 L/R, 只调末尾纯填充字符(接头字符原位保留); 内容行: 正文补/裁到 W-2 列, 左边线落在 L。
 * ⚠ 只动空格与边框填充, 不改正文文字; 左边界比规范列靠右时(前缀含刚性内容)放弃本行, 不硬裁。
 */
function rewriteRow(
  line: string,
  box: BoxRegion,
  rowIndex: number,
  geo: BoxGeo,
  ctx: RewriteCtx
): string {
  const cols = displayCols(line);
  const frameRow = isFrameRowOf(box, rowIndex);
  const { keyOf, geoCache, rowBoxList } = ctx;
  // 已处理框的规范列作排除集(绝对列, 不随行内容位移而失效)
  const claimed = new Set<number>();
  for (const other of rowBoxList) {
    if (other === box) continue;
    const g = geoCache.get(keyOf(other));
    if (!g) continue;
    claimed.add(g.L);
    claimed.add(g.R);
  }
  const leftIdx = locateLeftEdge(line, cols, frameRow, geo.L, claimed);
  if (leftIdx < 0) return line;
  // 右边线上限: 同行**兄弟框**中右邻框的**当前**左边界列 - 1
  //   ⚠ 用当前列而非规范列: 兄弟框此刻可能还没被搬到位(规范列更靠右),
  //   拿规范列当上限会把兄弟框的左角当成本框的右边线。
  let cap = Number.POSITIVE_INFINITY;
  for (const other of rowBoxList) {
    if (other === box) continue;
    const g = geoCache.get(keyOf(other));
    const otherL = g ? g.L : other.top.leftCol;
    if (otherL <= geo.L) continue; // 只管右边的
    if (isNestedIn(box, other)) continue; // 嵌套框不参与
    const peekClaimed = new Set<number>();
    for (const prev of rowBoxList) {
      const pg = geoCache.get(keyOf(prev));
      if (!pg || pg.L >= geo.L) continue;
      peekClaimed.add(pg.L);
      peekClaimed.add(pg.R);
    }
    const idx = locateLeftEdge(
      line,
      cols,
      isFrameRowOf(other, rowIndex),
      otherL,
      peekClaimed
    );
    const curL = idx >= 0 ? (cols[idx] as number) : otherL;
    cap = Math.min(cap, curL - 1);
  }
  const rightIdx = locateRightEdge(line, cols, frameRow, leftIdx, cap, claimed);
  if (rightIdx < 0 || rightIdx <= leftIdx) return line;
  const edge = edgeOf(line, cols, leftIdx, rightIdx);
  const prefix = line.slice(0, edge.leftIdx);
  const inner = line.slice(edge.leftIdx + 1, edge.rightIdx);
  const suffix = line.slice(edge.rightIdx + 1);
  // 前缀比规范左列还宽 → 前缀里有刚性内容(如 ▶), 不能裁 → 放弃本行(下一轮用更大的 L 重试)
  if (edge.leftCol > geo.L) return line;
  const newPrefix = prefix + ' '.repeat(geo.L - edge.leftCol);
  if (frameRow) {
    // 边线行: **只调末尾的纯填充字符**, 段内的接头字符(┬┴┼├┤…)原位保留。
    //   ⚠ 接头字符是作者画的"分支点", 抹掉会丢语义; 也不能挪位 ——
    //     下方竖线分支按它对齐(分支行不属于任何框的内容行 → 不会被重写 → 不会错位)。
    let fill = '-';
    for (const ch of inner) {
      if (HORIZONTAL_FILL_CHARS.has(ch)) {
        fill = ch;
        break;
      }
    }
    const target = Math.max(geo.W - 2, 0);
    const innerW = displayWidth(inner);
    let newInner = inner;
    if (innerW < target) {
      newInner = inner + fill.repeat(target - innerW);
    } else if (innerW > target) {
      // 从末尾裁纯填充字符(接头字符不裁); 裁不动(全是接头)时宁可不改, 也不删接头
      let need = innerW - target;
      let end = inner.length;
      while (
        need > 0 &&
        end > 0 &&
        HORIZONTAL_FILL_CHARS.has(inner[end - 1] as string)
      ) {
        end -= 1;
        need -= 1;
      }
      newInner = need > 0 ? inner : inner.slice(0, end);
    }
    const leftChar = line[edge.leftIdx] as string;
    const rightChar = line[edge.rightIdx] as string;
    return newPrefix + leftChar + newInner + rightChar + suffix;
  }
  const leftChar = line[edge.leftIdx] as string;
  const rightChar = line[edge.rightIdx] as string;
  const newInner = padOrTrimToWidth(inner, Math.max(geo.W - 2, 0));
  return newPrefix + leftChar + newInner + rightChar + suffix;
}

/**
 * 该块是否是"框线图"(可安全归一): 必须有**框角**。
 *   - Unicode 框角(┌┐└┘├┤┬┴┼…): 判据由 CORNER_CHARS 派生(单一真相源, 免两处各写一套);
 *   - 或 ASCII 框线的**整行**(如 "+------+" / "+-----+"), 避免把代码里的 '+--+' 误当框。
 * ⚠ 不用"含任意框线字符"当判据: 时序图(只有竖线+箭头)会被误判 → 生命线被挪位(实测误伤)。
 */
function hasBoxFrame(body: string[]): boolean {
  for (const line of body) {
    if (UNICODE_CORNER_RE.test(line)) return true;
    if (/^\s*\+[-+]{2,}\+\s*$/.test(line)) return true;
  }
  return false;
}

/**
 * 归一化 Markdown 中**围栏代码块内部**的框线图。
 * 围栏外内容一律不碰(表格/正文/行内代码原样)。
 */
export function normalizeMarkdownArt(markdown: string): string {
  if (!markdown) return markdown;
  if (!markdown.includes('```') && !markdown.includes('~~~')) return markdown;
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
    if (info.toLowerCase() === 'mermaid' || !hasBoxFrame(body)) {
      out.push(...body);
    } else {
      out.push(...fixLines(body));
    }
    out.push(lines[closeAt] as string);
    i = closeAt + 1;
  }
  const result = out.join('\n');
  return hadCRLF ? result.replace(/\n/g, '\r\n') : result;
}

/** 对齐一组行(一个围栏块/图区) —— 供外部调用与测试 */
export function reflowArt(lines: string[]): string[] {
  return fixLines(lines);
}

/**
 * 测试支撑导出: 每个框每行的右边线显示列(供单测断言"同框各行右边线同列")。
 * 生产渲染路径不调用本函数。
 */
export function analyzeBoxes(lines: string[]): Array<{
  top: number;
  bottom: number;
  rightCols: number[];
}> {
  const out = lines.map((l) => expandTabs(l));
  const borders = findBorders(out);
  const boxes = matchBoxes(borders, out);
  // 与主算法同口径: 逐行两阶段定位(逐框认领右边界), 否则内框会误取外框的右边线
  const rowBoxes = new Map<number, BoxRegion[]>();
  for (const box of boxes) {
    for (let r = box.top.lineIndex; r <= box.bottom.lineIndex; r += 1) {
      const arr = rowBoxes.get(r) ?? [];
      arr.push(box);
      rowBoxes.set(r, arr);
    }
  }
  const rightColOf = new Map<BoxRegion, Map<number, number>>();
  for (const [rowIndex, arr] of rowBoxes) {
    const line = out[rowIndex] as string;
    const rowEdges = locateRowEdges(
      line,
      rowIndex,
      arr,
      (box) => box.top.leftCol
    );
    for (const [box, edge] of rowEdges) {
      const per = rightColOf.get(box) ?? new Map<number, number>();
      per.set(rowIndex, edge.rightCol);
      rightColOf.set(box, per);
    }
  }
  return boxes.map((b) => {
    const per = rightColOf.get(b) ?? new Map<number, number>();
    const rightCols: number[] = [];
    for (let li = b.top.lineIndex; li <= b.bottom.lineIndex; li += 1) {
      rightCols.push(per.get(li) ?? -1);
    }
    return { top: b.top.lineIndex, bottom: b.bottom.lineIndex, rightCols };
  });
}
