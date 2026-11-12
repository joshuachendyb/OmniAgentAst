// 编辑历史: 2026-11-12 小欧 - 新建: Markdown 排版唯一规范代码(文档[30] 第 4/5/7 章落地)。
//   职责(SRP): 只做「排版规范 → CSS 变量」的解算, 不渲染、不取数、不管业务、不查设置。
//   唯一真源: ①全局字号阶梯 = utils/stepStyles 的 FontSize(本文件不自定义任何像素字号)
//            ②角色→档位映射 = 本文件 SCENES 表   ③间隔规范 = 本文件 SPACING 表
//            ④装饰裁剪矩阵 = 本文件 DECORATIONS 表
//   输出形态: **CSS 变量**(--md-*), 由 index.css 的 .md-body 作用域消费。
//     理由(文档[30] §2.4 的教训): 此前 MarkdownText 全部用内联 style 书写,
//     而 index.css 另有一套 .doc-body 类样式 → 两份真源互相压制(类样式被内联压死,
//     连带 !important 补丁)。本轮改为「TS 解算数字 → CSS 变量 → 单一 .md-body 类作用域」,
//     数字与颜色只在 TS 一处, CSS 只消费变量, **不再出现双源**。
//   其它文件(MarkdownText 等)只允许引用本文件解算结果, 不得另写字号数字/间距数字。
//
//   档位解算规则(与全局阶梯规范一致): 标题在阶梯上**相对正文上移 N 档**,
//   整组上界为 TITLE(20); 若上移后越界则整组向下顺延一档, 直至三者严格递减。
//   层级保障: h4/h5/h6 一律不再缩小字号, 只用字重+字色三层递减 → 从根上杜绝「标题小于正文」。
//
//   密度(界面密度设置项)只作用于**阅读区**(preview/doc)的间隔, **绝不触碰流水线**(chat/task):
//   流水线的段距/行高是老陈定案的信息流节奏, 属不可动项。

import type { CSSProperties } from 'react';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  FontWeight,
  MonoLineHeight,
  Radius,
} from '@/utils/stepStyles';
// 密度词表唯一真源(2026-11-12 小欧 - 文档[32]): 本文件不再自造 'comfortable' | 'compact' 字面量联合
import type { AppearanceDensity } from '@/constants/appearancePrefs';

// 2026-11-13 小欧 - 阅读区正文行高收口为唯一常量: preview/doc 两场景同值 1.6,
//   设置页预览小卡此前自写裸 1.6 构成第二真源, 现同源引用本常量。
export const READING_LINE_HEIGHT = 1.6;



/**
 * 阅读区内容块统一宽度上限(唯一定义点, px) —— 2026-11-13 小欧。
 *   背景: 文件预览面板宽由拖拽决定(左树 200~360 + flex 右栏), 1920 屏下右栏约 1500px。
 *         原 40em(560px) 钉在 .md-body 根容器 → 整页内容(含代码块/宽表)都只有 560px,
 *         右侧空掉近千像素, 屏幕资源浪费。
 *   裁定: **统一单栏 + 恒定窄边距** —— 段落/标题/代码块/表格/图片同宽同基线。
 *         ① 不按「文字/表格」分两档: 分档会造成宽窄不一(文字只占左侧一条、表格满宽),
 *            基线参差、观感割裂, 且空白集中在一侧。
 *         ② **留白用固定窄边距, 不用比例也不用 margin auto 均分** ——
 *            比例留白在宽屏下会把内容推成窄条; margin auto 均分在容器 < 上限时归零(内容贴边),
 *            两者都造成「留白忽大忽小」。现由 READING_GUTTER_PX 恒定左右各留一道窄边距。
 *         ③ 上限 1800px: 覆盖 1920 屏的面板宽(约 1500px)不再人为截断;
 *            仅 2560 屏等超宽场景封顶, 避免一行拉到 200+ 字完全不可读(居中均分剩余)。
 *   流水线(chat/task)不设上限、不加边距 → 满宽, 行为与改前完全一致。
 */
export const READING_MEASURE_MAX_PX = 1800;

/**
 * 阅读区内容块左右恒定边距(唯一定义点, px) —— 2026-11-13 小欧。
 *   语义: 「有边距但不浪费」—— 24px 既保证文字不贴容器边框(留一道设计过的窄边),
 *         又几乎不占屏幕(1920 屏面板约 1500px 时, 内容仍占约 96%)。
 *         叠加文件预览容器自身 padding 8px + 边框 1px, 文字距面板外沿共约 33px。
 */
export const READING_GUTTER_PX = 24;



/** 排版场景(每个场景 = 从全局阶梯中取用的一段连续区间) */
export type MdScene = 'preview' | 'doc' | 'chat' | 'task';

/** 全局阶梯档位名(按像素升序) —— 取值全部来自 utils/stepStyles, 本文件不写裸数字 */
export type MdTier =
  | 'CAPTION'
  | 'SMALL'
  | 'SECONDARY'
  | 'PRIMARY'
  | 'SUBHEAD'
  | 'HEADING'
  | 'TITLE';

/** 全局阶梯升序表(档位 → 像素) */
const LADDER: ReadonlyArray<{ tier: MdTier; px: number }> = [
  { tier: 'CAPTION', px: FontSize.CAPTION },
  { tier: 'SMALL', px: FontSize.SMALL },
  { tier: 'SECONDARY', px: FontSize.SECONDARY },
  { tier: 'PRIMARY', px: FontSize.PRIMARY },
  { tier: 'SUBHEAD', px: FontSize.SUBHEAD },
  { tier: 'HEADING', px: FontSize.HEADING },
  { tier: 'TITLE', px: FontSize.TITLE },
];

const TIER_INDEX: Record<MdTier, number> = LADDER.reduce(
  (acc, item, idx) => {
    acc[item.tier] = idx;
    return acc;
  },
  {} as Record<MdTier, number>
);

/** 基准字号(正文档位) → 阶梯档位 */
const BASE_TIER: Record<number, MdTier> = {
  [FontSize.SECONDARY]: 'SECONDARY',
  [FontSize.PRIMARY]: 'PRIMARY',
  [FontSize.SUBHEAD]: 'SUBHEAD',
};

/** 标题相对正文的**阶梯档数**偏移(上移为正) */
interface TitleOffsets {
  h1: number;
  h2: number;
  h3: number;
}

/** 场景间隔规范(像素) —— 依据见文档[30] 第 4.5 节 */
interface SceneSpacing {
  /** 正文行高倍数 */
  lineHeight: number;
  /** 段落间距 */
  paraGap: number;
  /** 标题上间距 */
  headTop: number;
  /** 标题下间距 */
  headBottom: number;
  /** 列表项间距 */
  listGap: number;
  /** 嵌套列表缩进 */
  indent: number;
  /** 表格单元格内距(竖/横) */
  cellPadY: number;
  cellPadX: number;
  /** 代码块内距(竖/横) */
  codePadY: number;
  codePadX: number;
  /** 引用块内距(竖/横) */
  quotePadY: number;
  quotePadX: number;
  /** 代码块行高倍数 */
  codeLineHeight: number;
}

/** 装饰裁剪矩阵(文档[30] 第 7 章) —— 颜色全部复用既有 Colors 令牌, 不新增颜色令牌 */
interface SceneDecorations {
  h1Divider: boolean;
  h2Divider: boolean;
  inlineCodeBg: boolean;
  quoteBg: boolean;
  tableHeadBg: boolean;
  tableZebra: boolean;
  codeLangLabel: boolean;
  /** 任务列表复选框 */
  taskCheckbox: boolean;
}

interface SceneConfig {
  /** 正文档位: 固定值(流水线) 或随「阅读区字号」设置项浮动(阅读区) */
  fixedBase?: number;
  baseAdjustable: boolean;
  /** 标题档位偏移 */
  titleOffsets: TitleOffsets;
  /** 表格字号相对正文的阶梯档差(负=更小) */
  tableOffset: number;
  /** 行内代码字号档位 */
  inlineCodeTier: MdTier;
  /** 成段文字是否限行宽: true = 按 clamp(下限, 62%, 上限) 夹逼; false = 满宽(流水线) */
  proseLimit: boolean;
  spacing: SceneSpacing;
  decorations: SceneDecorations;
}

const SCENES: Record<MdScene, SceneConfig> = {
  // 文件浏览器 md 美显: 全集(中→超大), 宽松
  preview: {
    baseAdjustable: true,
    titleOffsets: { h1: 3, h2: 2, h3: 1 },
    tableOffset: 0,
    inlineCodeTier: 'SECONDARY',
    proseLimit: true,
    spacing: {
      lineHeight: READING_LINE_HEIGHT,
      paraGap: 8,
      headTop: 16,
      headBottom: 8,
      listGap: 4,
      indent: 16,
      cellPadY: 4,
      cellPadX: 8,
      codePadY: 8,
      codePadX: 12,
      quotePadY: 8,
      quotePadX: 12,
      codeLineHeight: 1.4,
    },
    decorations: {
      h1Divider: true,
      h2Divider: true,
      inlineCodeBg: true,
      quoteBg: true,
      tableHeadBg: true,
      tableZebra: true,
      codeLangLabel: true,
      taskCheckbox: true,
    },
  },
  // 设置页安全说明弹框: 中→特大, 中等
  doc: {
    baseAdjustable: true,
    titleOffsets: { h1: 2, h2: 1, h3: 0 },
    tableOffset: 0,
    inlineCodeTier: 'SECONDARY',
    proseLimit: true,
    spacing: {
      lineHeight: READING_LINE_HEIGHT,
      paraGap: 8,
      headTop: 12,
      headBottom: 8,
      listGap: 4,
      indent: 16,
      cellPadY: 4,
      cellPadX: 8,
      codePadY: 8,
      codePadX: 12,
      quotePadY: 8,
      quotePadX: 12,
      codeLineHeight: 1.4,
    },
    decorations: {
      h1Divider: true,
      h2Divider: true,
      inlineCodeBg: true,
      quoteBg: true,
      tableHeadBg: true,
      tableZebra: false,
      codeLangLabel: true,
      taskCheckbox: true,
    },
  },
  // 流水线正文(答复段 + 思考段): 中→大, 紧(密度绝不触碰)
  chat: {
    fixedBase: FontSize.PRIMARY,
    baseAdjustable: false,
    titleOffsets: { h1: 1, h2: 1, h3: 0 },
    tableOffset: -1,
    inlineCodeTier: 'SECONDARY',
    proseLimit: false,
    spacing: {
      lineHeight: 1.35,
      paraGap: 4,
      headTop: 8,
      headBottom: 4,
      listGap: 2,
      indent: 12,
      cellPadY: 3,
      cellPadX: 6,
      codePadY: 6,
      codePadX: 8,
      quotePadY: 4,
      quotePadX: 8,
      codeLineHeight: 1.35,
    },
    decorations: {
      h1Divider: true,
      h2Divider: false,
      inlineCodeBg: true,
      quoteBg: false,
      tableHeadBg: false,
      tableZebra: false,
      codeLangLabel: false,
      taskCheckbox: true,
    },
  },
  // 任务卡回复区: 小→中, 紧(密度绝不触碰)
  task: {
    fixedBase: FontSize.SECONDARY,
    baseAdjustable: false,
    titleOffsets: { h1: 1, h2: 1, h3: 1 },
    tableOffset: -1,
    inlineCodeTier: 'SMALL',
    proseLimit: false,
    spacing: {
      lineHeight: 1.5,
      paraGap: 4,
      headTop: 6,
      headBottom: 4,
      listGap: 2,
      indent: 12,
      cellPadY: 3,
      cellPadX: 6,
      codePadY: 6,
      codePadX: 8,
      quotePadY: 4,
      quotePadX: 8,
      codeLineHeight: 1.35,
    },
    decorations: {
      h1Divider: true,
      h2Divider: false,
      inlineCodeBg: false,
      quoteBg: false,
      tableHeadBg: false,
      tableZebra: false,
      codeLangLabel: false,
      taskCheckbox: true,
    },
  },
};

/**
 * 代码块行为样式(P3 定案: **横向滚动**而非折行) —— 唯一真源。
 *   依据(2026-10-05 老陈裁定「二选一」): wordBreak:normal 与 overflow:auto 语义相消,
 *   折行与横向滚动只能取一 → 取横向滚动(长代码行不折断, 容器出滚动条)。
 *   为什么必须由 TS 出、而不是写在 index.css 的 .md-body pre 里:
 *     ①max-height 400px 是**数字**, 写在 CSS 里即违[30]「数字与颜色只在 TS 一处, CSS 只消费变量」;
 *     ②这四项是**行为**属性(不折行/滚动/限高), 与排版字号阶梯不同族, 由本文件单点给出,
 *       CSS 侧不再声明 → 全站唯一真源, 不存在「类样式与内联各写一份」的压制隐患。
 *   视觉零变化: 数值与 index.css 原声明完全一致(pre / normal / auto / 400px)。
 */
export const codeBlockStyle = {
  whiteSpace: 'pre',
  wordBreak: 'normal',
  overflow: 'auto',
  maxHeight: '400px',
} as const;

/**
 * 密度系数(阅读区间隔随密度松紧; 流水线不消费)
 *   2026-11-12 小欧 - 密度词表类型改引 constants/appearancePrefs 的 AppearanceDensity:
 *     原为字面量联合 'comfortable' | 'compact', 与 appearancePrefs 的词表构成第二份真源
 *     (新增/改名一档须改两处, 必然漂移) → 现只保留一份词表。
 *   本文件是阅读区间距系数的**唯一真源**(原 utils/density.ts 有一份副本, 已随该文件删除)。
 */
export const DENSITY_PAD: Record<AppearanceDensity, number> = {
  comfortable: 1,
  compact: 0.75,
};

/** 密度缩放后的间隔取整到 2px 档(不得出现游离半像素) */
const scaleSpacing = (value: number, pad: number): number => {
  const scaled = value * pad;
  const snapped = Math.round(scaled / 2) * 2;
  return Math.max(2, snapped);
};

/** 解算结果: CSS 变量 + 场景 class 名 */
export interface MdStyleBundle {
  scene: MdScene;
  /** 施加在 .md-body 根节点上的 CSS 变量 */
  vars: CSSProperties;
  /** 根节点 class(场景后缀供 CSS 做装饰裁剪) */
  rootClass: string;
  /** 代码块行高倍数(普通代码; 含框线图时另取 1.1) */
  codeLineHeight: number;
  /** 装饰开关(渲染层按此决定是否加语言标签/斑马等) */
  decorations: SceneDecorations;
}

/** 标题在阶梯上相对正文上移 N 档; 越界则整组顺延一档(保证严格递减) */
const resolveTitleTiers = (bodyTierIdx: number, offsets: TitleOffsets) => {
  const top = TIER_INDEX.TITLE;
  let h3 = bodyTierIdx + offsets.h3;
  let h2 = bodyTierIdx + offsets.h2;
  let h1 = bodyTierIdx + offsets.h1;
  while (h1 > top) {
    h1 -= 1;
    h2 -= 1;
    h3 -= 1;
  }
  const px = (idx: number): number =>
    (LADDER[Math.min(Math.max(idx, 0), LADDER.length - 1)] as { px: number })
      .px;
  return { h1: px(h1), h2: px(h2), h3: px(h3) };
};

/**
 * 解算某场景在某正文档位下的排版变量。
 * @param scene 排版场景
 * @param base  正文档位像素(仅 baseAdjustable 场景生效; 缺省取 14)
 * @param density 密度档(仅阅读区影响间隔)
 */
export const mdStyles = (
  scene: MdScene,
  base?: number,
  density: AppearanceDensity = 'comfortable'
): MdStyleBundle => {
  const cfg = SCENES[scene];
  const bodyPx = cfg.baseAdjustable
    ? (base ?? FontSize.PRIMARY)
    : (cfg.fixedBase ?? FontSize.PRIMARY);
  const bodyTier = BASE_TIER[bodyPx] ?? 'PRIMARY';
  const bodyIdx = TIER_INDEX[bodyTier];
  const titlePx = resolveTitleTiers(bodyIdx, cfg.titleOffsets);

  // 阅读区间隔随密度缩放(取整到 2px 档); 流水线固定值, 密度绝不触碰
  const pad = cfg.baseAdjustable ? DENSITY_PAD[density] : 1;
  const sp = cfg.spacing;
  const spacing: SceneSpacing = cfg.baseAdjustable
    ? {
        ...sp,
        paraGap: scaleSpacing(sp.paraGap, pad),
        headTop: scaleSpacing(sp.headTop, pad),
        headBottom: scaleSpacing(sp.headBottom, pad),
        listGap: scaleSpacing(sp.listGap, pad),
        indent: scaleSpacing(sp.indent, pad),
        cellPadY: scaleSpacing(sp.cellPadY, pad),
        cellPadX: scaleSpacing(sp.cellPadX, pad),
        codePadY: scaleSpacing(sp.codePadY, pad),
        codePadX: scaleSpacing(sp.codePadX, pad),
        quotePadY: scaleSpacing(sp.quotePadY, pad),
        quotePadX: scaleSpacing(sp.quotePadX, pad),
      }
    : sp;

  const dec = cfg.decorations;
  const inlineCodePx = (
    LADDER[TIER_INDEX[cfg.inlineCodeTier]] as { px: number }
  ).px;
  const tableIdx = Math.min(
    Math.max(bodyIdx + cfg.tableOffset, 0),
    LADDER.length - 1
  );
  const tablePx = (LADDER[tableIdx] as { px: number }).px;

  const vars = {
    '--md-fs-body': `${bodyPx}px`,
    '--md-fs-h1': `${titlePx.h1}px`,
    '--md-fs-h2': `${titlePx.h2}px`,
    '--md-fs-h3': `${titlePx.h3}px`,
    '--md-fs-h4': `${bodyPx}px`,
    '--md-fs-h5': `${bodyPx}px`,
    '--md-fs-h6': `${bodyPx}px`,
    '--md-fs-inline-code': `${inlineCodePx}px`,
    '--md-fs-table': `${tablePx}px`,
    '--md-fs-code-block': `${FontSize.CODE}px`,
    '--md-lh-body': `${spacing.lineHeight}`,
    '--md-lh-code-block': `${spacing.codeLineHeight}`,
    '--md-gap-para': `${spacing.paraGap}px`,
    '--md-gap-head-top': `${spacing.headTop}px`,
    '--md-gap-head-bottom': `${spacing.headBottom}px`,
    '--md-gap-list': `${spacing.listGap}px`,
    '--md-indent': `${spacing.indent}px`,
    '--md-pad-cell-y': `${spacing.cellPadY}px`,
    '--md-pad-cell-x': `${spacing.cellPadX}px`,
    '--md-pad-code-y': `${spacing.codePadY}px`,
    '--md-pad-code-x': `${spacing.codePadX}px`,
    '--md-pad-quote-y': `${spacing.quotePadY}px`,
    '--md-pad-quote-x': `${spacing.quotePadX}px`,
    // 阅读区内容块统一宽度上限: min(100%, 1800px) —— 窄面板自然收缩到面板宽,
    //   宽面板封顶防超宽屏一行拉到 200+ 字。全部内容同宽同基线, **不分档**。
    '--md-measure': cfg.proseLimit
      ? `min(100%, ${READING_MEASURE_MAX_PX}px)`
      : 'none',
    // 阅读区左右恒定窄边距: 预览/文档场景 24px(有边距但不浪费), 流水线 0(零视觉变化)
    '--md-gutter': cfg.proseLimit ? `${READING_GUTTER_PX}px` : '0px',
    '--md-radius': `${Radius.SM}px`,
    // 章节分隔线: h1 全场景; h2 仅阅读区(装饰裁剪矩阵)
    '--md-h1-divider': `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
    '--md-h2-divider': dec.h2Divider
      ? `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`
      : 'none',
    '--md-h2-divider-pad': dec.h2Divider ? `${spacing.headBottom}px` : '0px',
    // 颜色全部引既有 Colors 令牌(不新增颜色令牌)
    '--md-color-text': Colors.TEXT.PRIMARY,
    '--md-color-title': Colors.TEXT.STRONG,
    '--md-color-title-soft': Colors.TEXT.PRIMARY,
    '--md-color-code': Colors.TEXT.STRONG,
    '--md-color-code-bg': dec.inlineCodeBg ? Colors.BG.TERTIARY : 'transparent',
    '--md-color-code-block-bg': Colors.BG.SECONDARY,
    '--md-color-code-accent': dec.inlineCodeBg
      ? Colors.BORDER.ACCENT
      : 'transparent',
    '--md-color-quote-bg': dec.quoteBg ? Colors.BG.SECONDARY : 'transparent',
    '--md-color-border': Colors.BORDER.DEFAULT,
    '--md-color-divider': Colors.BORDER.LIGHT,
    '--md-color-quote-bar': Colors.BORDER.VERTICAL,
    '--md-color-table-head-bg': dec.tableHeadBg
      ? Colors.BG.TERTIARY
      : 'transparent',
    '--md-color-zebra': dec.tableZebra ? Colors.BG.SECONDARY : 'transparent',
    '--md-color-link': Colors.PRIMARY,
    '--md-color-selection-bg': Colors.BG.SELECTED,
    '--md-color-selection-fg': Colors.TEXT.STRONG,
    '--md-font-mono': FontFamily.MONO,
    '--md-border-w': `${BorderWidth.THIN}px`,
    '--md-border-w-thick': `${BorderWidth.THICK}px`,
  } as CSSProperties;

  return {
    scene,
    vars,
    rootClass: `md-body md-${scene}`,
    codeLineHeight: spacing.codeLineHeight,
    decorations: dec,
  };
};

/** 标题字重/字色三层递减(h4/h5/h6 不再缩字号) —— 字重上限 600(中文无 700 真字重) */
export const TITLE_WEIGHTS = {
  h1: FontWeight.BOLD,
  h2: FontWeight.BOLD,
  h3: FontWeight.BOLD,
  h4: FontWeight.BOLD,
  h5: FontWeight.MEDIUM,
  h6: FontWeight.REGULAR,
} as const;

/** ASCII 框线图判定: 围栏内含框线字符时行高须降到 MonoLineHeight(竖线否则断成虚线) */
export const containsBoxArt = (text: string): boolean =>
  /[│┃║┌┐└┘├┤┬┴┼╔╗╚╝]/.test(text);

/** 围栏代码块行高: 普通代码取场景值; 含框线图取 MonoLineHeight(1.1) —— 不可破 */
export const codeFenceLineHeight = (
  content: string,
  fallback: number
): number => (containsBoxArt(content) ? MonoLineHeight : fallback);

/** 表格单元格是否数字列(右对齐 + 等宽数字) */
export const isNumericCell = (content: string): boolean => {
  const text = content.replace(/[\s,]/g, '');
  if (!text) return false;
  return /^[-+]?\d*\.?\d+(%?)$/.test(text);
};
