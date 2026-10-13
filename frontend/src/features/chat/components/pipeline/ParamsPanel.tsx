// 编辑历史: 2026-10-13 小欧 - 新建: 工具参数浮层面板(文档[29] §3.5/DC-05/DC-06/DC-16/DC-19/DC-21/DC-22)
//   乙·分组卡片(默认) / 甲·规格表 可切 · 五类语义分组 · 巨型值折叠限高 · 复制为 key=value 逐行 — 小欧 2026-10-13
// 编辑历史: 2026-10-13 小欧 - 十三轮迭代(北京老陈逐条裁定, 每条均有真实像素截图佐证), 摘要如下:
//   ①【折叠铁律】只有**含换行**的值才可折叠(isHugeValue); 对象/数组与超长字符串**一律不折叠** ——
//     此前把「分类用 isPayload」与「可否折叠用 isHugeValue」合并成一个布尔量, 导致 meta/command 也带折叠箭头(违反), 已拆开;
//   ②长行**折行完整显示**: PlainValue 与两视图的 key/值列一律 pre-wrap + break-word, 全组件无 ellipsis/nowrap;
//   ③对象用**紧凑单行 JSON**(JSON.stringify(v) 无缩进): 原 2 空格缩进让 3 键对象占 8 行且撑宽面板(fit-content), 实测后改;
//   ④空值「(空)」用 TEXT.TERTIARY 与真实值(PRIMARY)分色, 避免与 false/0 混淆;
//   ⑤分组类渲染顺序改为 路径→开关→编码→正文载荷→其他(原照搬 categorize 的**判定优先级**, 正文载荷跑到了最前);
//     色条统一 BORDER.STRONG(原 5 档中性灰在 #fafafa 底上 #e8e8e8/#f0f0f0 对比度仅 1.1/1.05:1 等于看不见, 且开关与编码同档);
//   ⑥规格表 key 列去 textAlign:'right' 改**左对齐**(与 §2.3 示意图一致、且与分组视图 96px key 列口径统一);
//   ⑦规格表巨型值**整宽跨行**: 行容器加 flexWrap + ValuePre 的 flexBasis:100%, 展开态由 SpecView 自管 openKeys(Set);
//     折叠行/代码块/普通值拆成 ValueToggle/ValuePre/PlainValue 三件供两视图复用, 不写两套折叠逻辑(DRY);
//   ⑧面板外壳: 自带 BG.SECONDARY+BORDER.DEFAULT+Radius.SM 卡片规格(DC-19), 根不挂等宽字体(免污染标题/分类标签),
//     外壳 maxHeight:calc(100vh-58px) + 内容区滚动 —— 行数一个不裁剪, 但浮层 portal 脱离右栏滚动容器,
//     完全不限会超出视口不可达;
//     2026-10-14 小欧 订正: 原写 calc(100vh-32px), 实值已改 58 —— 58 = 留白32 + antd inner padding 24 + 边框2,
//     详见下方 2026-10-14 编辑历史
//   ⑨面板头: 分组/规格表(Segmented 24px)、复制(≈20px)、✕(≈16px) 统一包进 24px 居中盒(HEADER_CTRL_BOX)对齐基线;
//     装饰图标 </> 由 PRIMARY 蓝改 TEXT.SECONDARY 中性灰(蓝在本系统=可点, 装饰用蓝会误导), 工具名去 nowrap 改折行(注: 2026-10-13 23:20 依北京老陈"不许折行"裁定**改回 nowrap**, 见下方编辑历史) — 小欧-2026-10-13
// 编辑历史: 2026-10-13 小欧 - 文档[29]§6.10 新增第三个视图「结果」(工具原始结果 raw_data):
//   ① PARAMS_VIEW_MAP/VIEW_OPTIONS 增第三个标签 result;
//   ② 值渲染模式抽 ValueMode('param'|'result') 依赖注入(OCP), 默认 'param' 时文本取 fullTextOf、容器样式逐像素不变,
//      规格表样式不被结果视图污染; 结果模式对象/数组走 NestedRows 递归折叠 + diff 行级增删着色;
//   ③ 折叠判定抽 isFoldable(v, mode): 参数模式零变化(isHugeValue), 结果模式额外让非空对象/数组可折;
//   ④ 仅隐藏 base64_data(MB 级, 纯体积原因); 下划线键**全部放行**(撤销前缀过滤, 见下方 2026-10-14 两条);
//   ⑤ 结果视图**绝不兜底**: result 空/未传 → entries 空数组 → 显示「本次工具执行：<summary>」(非空白);
//   ⑥ 复制按视图分支: 结果视图复制 raw_data 缩进 JSON(**不是**过滤后的视图 —— 复制的是原始数据);
//   ⑦ 标题改 whiteSpace:nowrap + flexShrink:0(北京老陈"不许折行不许折行"), maxW 640→720 配合;
//   ⑧ 空串在结果模式下也给 `(空)` 占位(否则用户分不清"本来就没有"还是"渲染漏了"; 命中常态空 stderr);
//   ⑨ 数组摘要用 `[]` 不用 `{}`(23 处 rows[]/matches[] 类字段); 空容器不配折叠箭头(fold 开一个空数组无意义).
//   审计修正: 文件头概述与下方 ⑦ 的结论相反(头写"工具名改折行"), 已加注说明结论已反转 — 小欧-2026-10-13
// 编辑历史: 2026-10-14 小欧 - 浮层纵向居中后修正外壳封顶: calc(100vh-32px) → calc(100vh-58px)。
//   封顶值须扣 58 = 留白32 + antd inner padding 24 + 本外壳边框2(padding:0 只归零卡片自身, 去不掉 inner 的)。
//   另撤销下划线私有键过滤、补非 dict 防御。
//   2026-10-14 小欧 订正: 原写「包裹层总高实为视口-6, 差 6px 即上下同时被切」—— 差值应为 26(58-32),
//   且总高 100vh-6 < 视口, 居中后本不会被切; 真实后果是上下留白由 32px 缩到 3px(视觉贴顶贴底) — 小欧-2026-10-14
// 编辑历史: 2026-10-14 小欧 - 结果视图**递归折叠渲染**(北京老陈裁定, 独立组件 NestedRows/NestedRow/SpecView 之外):
//   病根 tree.children / get_db_schema.tables[].columns[] / read_xlsx.sheets[] 等递归结构原用
//   JSON.stringify 整块展开, 缩进随深度累积成"斜坡"且行数暴涨。故容器逐层独立折叠、默认全折叠;
//   数组元素全为对象时下标降为不可点分组标题(纯结构判断, 不猜哪列是标题), 否则要点击才看到一个目录名。
//   仅 valueMode='result' 生效, 参数视图零影响。
// 编辑历史: 2026-10-14 小欧 - 默认标签由「分组参数」改为「**TOOL结果**」(北京老陈裁定)。记忆规则不变:
//   result 仍不落盘, 切到分组/规格表才记住。原「不记忆 result」的理由(20 个工具 raw_data 为 {} 会落空白页)
//   **已不成立** —— 空态现显示「本次工具执行：<summary>」。小欧
import React, { useMemo, useState } from 'react';
import { Segmented } from 'antd';
import { CloseOutlined, CodeOutlined } from '@ant-design/icons';
import { CircleArrow } from '@/components/CircleArrow';
import { CopyButton } from '@/components/markdown/CopyButton';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  Radius,
  Spacing,
} from '@/utils/stepStyles';

// ==================== 模块级常量(防每次渲染重建, 同 REJECT_LABEL_MAP 范式) ====================

/** 巨型值字符阈值(判定阈值非视觉令牌, 故不入 stepStyles — §3.4.3) */
const HUGE_VALUE_CHARS = 200;

/**
 * 2026-10-13 小欧 - 六分类(北京老陈裁定 B 案 + 「重要参数不许进其他」铁律)。
 *   旧版 4 具名 + 「其他」: 用全仓 80+ 工具真实参数实测, 「其他」是最大的桶
 *   (bash 5 个参数 4 个进其他 / http_get 6 个进 4 个 / query_sql 6 个进 4 个), 分组失去意义。
 *   本版据实测把高频参数**显式列入 key 集合**, 使「其他参数」只接真正零散项。
 */
const PATH_KEYS: ReadonlySet<string> = new Set([
  'path',
  'dir_path',
  'file_path',
  'source_path',
  'dest',
  'output_path',
  // 2026-10-13 新增: 旧版漏判导致 cwd/url/source/target 掉进「其他」(实测 bash.cwd、http_get.url)
  'cwd',
  'url',
  'source',
  'target',
  'directory',
  'dir',
  'sql_file',
]);

/** 正文载荷: 主内容字段。**显式列 key** —— 否则短命令(ls / git status)抓不到 payload 判定, 会掉进「其他」 */
const PAYLOAD_KEYS: ReadonlySet<string> = new Set([
  'content',
  'body',
  'command',
  'sql',
  'data',
  'prompt',
  'message',
  'text',
  'script',
  'code',
  'value',
  'old_string',
  'new_string',
  'table_data',
  'slides',
  'operations',
  'conditions',
  'select_columns',
  'region',
  'action',
]);

/** 检索条件: 找什么 / 怎么匹配 / 怎么排 */
const SEARCH_KEYS: ReadonlySet<string> = new Set([
  'pattern',
  'glob',
  'regex',
  'query',
  'ignore_case',
  'case_sensitive',
  'sort_by',
  'group_by',
  'allowed_domains',
  'blocked_domains',
  'extract_format',
  'info_type',
  'level',
  'source',
]);

/** 执行控制: 跑多少 / 跑多久 / 怎么跑 */
const EXEC_KEYS: ReadonlySet<string> = new Set([
  'timeout',
  'offset',
  'limit',
  'tail',
  'delay',
  'interval',
  'count',
  'depth',
  'max_depth',
  'retries',
  'num_results',
  'dry_run',
  'page',
  'pages',
  'slide',
  'sheet',
  'sheet_name',
  'shell_type',
  'method',
  'proxy',
  'success_codes',
  'mode',
  'unit',
  'start',
  'end',
  'year',
  'name',
  'width',
  'height',
  'x',
  'y',
  'amount',
  'direction',
]);

/** 格式与编码: 怎么解释这份数据。**不砍成「其他」** —— 2026-10-13: 全仓 6 个工具有 encoding,
 *  砍掉就会让 encoding/charset 掉进兜底桶, 违反「重要参数不许进其他」 */
const FORMAT_KEYS: ReadonlySet<string> = new Set([
  'encoding',
  'charset',
  'format',
  'output_format',
  'date_format',
]);

// 2026-10-13 23:00 小欧 - 文档[29]§6.10: 第三个标签「结果」渲染工具原始结果(raw_data)
export const PARAMS_VIEW_MAP = {
  group: '分组参数',
  spec: '规格表参数',
  result: 'TOOL结果',
} as const;
export type ParamsView = keyof typeof PARAMS_VIEW_MAP;
/**
 * 2026-10-13 小欧 - 核查订正: 此数组**不可加 `as const`**。
 *   `as const` 会产出 readonly tuple, 而 antd `Segmented.options` 的类型是
 *   `(string | number | SegmentedOption)[]`(可变数组) → readonly 不可赋值, tsc 报 TS2322。
 *   故去掉 `as const`, 让元素结构按推断走(仍能提供 label/value 字面量类型)。
 */
const VIEW_OPTIONS = [
  { label: PARAMS_VIEW_MAP.group, value: 'group' },
  { label: PARAMS_VIEW_MAP.spec, value: 'spec' },
  { label: PARAMS_VIEW_MAP.result, value: 'result' },
];

/**
 * 面板头控件统一盒: 与 antd `Segmented size="small"` 同高(controlHeightSM=24)。
 * 2026-10-13 小欧 - 实测截图: Segmented 24px / CopyButton≈20px / ✕≈16px 三者直接并排,
 *   顶端与底端都不齐, 观感粗糙。统一包成 24px 居中盒后三者基线对齐(内容居中, 盒高一致)。
 */
const HEADER_CTRL_BOX: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  height: 24,
};

/** 2026-10-13 小欧 - DC-21: 分类色只用 BORDER 中性灰阶, 语义色(警告/错误/成功)保留给状态 */
type Category =
  | 'path'
  | 'switch'
  | 'payload'
  | 'search'
  | 'exec'
  | 'format'
  | 'other';
const CATEGORY_META: ReadonlyArray<{
  id: Category;
  label: string;
  color: string;
}> = [
  // 2026-10-13 小欧 - 十四轮(北京老陈「重要的在上面」+ 「其他」改「补充参数」):
  //   ①显示顺序按**重要性**重排(下方数组即渲染顺序; categorize 按 id 显式 return, 与本顺序无关,
  //     调序零风险)。排序依据 = 排查时的关注度 × 实测占比(216 个真实参数):
  //       路径 18.5% / 正文载荷 24.1% / 执行控制 21.8% / 开关 7.4% / 检索条件 6.0% / 格式 2.3%。
  //     路径置于正文载荷之上: 文件类工具里「改的是哪个文件」是理解一切的锚点, 先看路径再看内容。
  //   ②「其他」→「补充参数」: 原名零信息量; 「补充」表明它是补充项而非主参数, 不误导。
  //   ③色条统一 BORDER.STRONG: 原 5 档中性灰在 #fafafa 底上 #e8e8e8/#f0f0f0 对比度仅 1.1/1.05:1
  //     等于看不见, 且开关与编码本就同档无区分; 设计 §3.5.2 原文本即写"类名靠文字区分",
  //     故色条只当分组锚点、不承担分类编码。仍取自 Colors.BORDER.*(DC-21/T30 不违), 不新增颜色
  { id: 'path', label: '路径', color: Colors.BORDER.STRONG },
  { id: 'payload', label: '正文载荷', color: Colors.BORDER.STRONG },
  { id: 'exec', label: '执行控制', color: Colors.BORDER.STRONG },
  { id: 'switch', label: '开关', color: Colors.BORDER.STRONG },
  { id: 'search', label: '检索条件', color: Colors.BORDER.STRONG },
  { id: 'format', label: '格式', color: Colors.BORDER.STRONG },
  { id: 'other', label: '补充参数', color: Colors.BORDER.STRONG },
];

// ==================== 值格式化(纯函数, 可单测) ====================

/** 「路径特征」: 同时含分隔符 **且** 末段有扩展名(§2.3.2 细则, 防误伤 SQL/代码片段) */
const isPathLike = (v: string): boolean => {
  if (!/[\\/]/.test(v)) return false;
  const last = v.split(/[\\/]/).pop() ?? '';
  return /\.[A-Za-z0-9]{1,8}$/.test(last);
};

/**
 * 巨型值判定 = **值含换行**(如 content 的多行代码块)。
 * 2026-10-13 小欧 - 北京老陈裁定: **只有 content 这类巨型参数才允许折叠/展开控制**, 其余参数
 *   一律**不许折叠** —— 长单行值(如 shell command)折行完整显示, 小对象(meta 等)直接展开格式化 JSON。
 *   初稿把「对象/数组」与「>200 字符」也判成巨型, 导致 meta/command 都带折叠箭头(实测截图证据),
 *   违反裁定, 本轮删掉这两条: ①对象不再折叠, 直接 JSON 展示; ②字符阈值已删(长值靠折行不靠折叠)。
 */
const isHugeValue = (v: unknown): boolean =>
  typeof v === 'string' && v.includes('\n');

/**
 * 「正文载荷」分类判定(§2.3.2 设计原义, 与**折叠**无关):
 *   含换行 / 值为 list|dict / 超长字符。对象仍归 payload 类, 只是**不再因此获得折叠能力**。
 */
const isPayload = (v: unknown): boolean =>
  (typeof v === 'object' && v !== null) ||
  (typeof v === 'string' && (v.includes('\n') || v.length > HUGE_VALUE_CHARS));

/**
 * 判定优先级链(十三轮重排): 严格自上而下, 命中即止, 防一个参数落进两组。
 *
 * 排期理由(每一步都在防一个实测到的误判):
 *   1. **开关** 提到最前 —— 值是 boolean 是最硬的特征, 且 append/recursive/overwrite/dry_run 这类
 *      既在 EXEC_KEYS 又天然是开关, 按 key 判会错列;
 *   2. **正文载荷**第二 —— 必须早于路径: command/old_string 这类长文本里常含 `F:\x\a.py`,
 *      若先判 isPathLike 会把整条命令误归「路径」(实测 `git show fa644f85 -- backend/…/x.py`);
 *   3. **路径**第三(主参数靠 key 命中, 值的形态判定只作补充);
 *   4~5. 检索条件 / 执行控制 纯 key 判定;
 *   6. **格式**(encoding/charset/format);
 *   7. **补充参数**(兜底) —— 只接真正零散项(实测剩 button/hive/timer_id 等场景参数, 无一主参数),
 *      主参数已全部显式列入上面 6 组 key 集合。
 */
const categorize = (k: string, v: unknown): Category => {
  if (typeof v === 'boolean') return 'switch';
  if (isPayload(v) || PAYLOAD_KEYS.has(k)) return 'payload';
  if (PATH_KEYS.has(k) || (typeof v === 'string' && isPathLike(v)))
    return 'path';
  if (SEARCH_KEYS.has(k)) return 'search';
  if (EXEC_KEYS.has(k)) return 'exec';
  if (FORMAT_KEYS.has(k)) return 'format';
  return 'other';
};

/** 2026-10-13 23:55 小欧 - 数组摘要用 `[]` 不用 `{}`(23 个 `rows[]`/`matches[]` 类字段)。
 *  参数视图零影响: 参数模式下 summaryOf 只被字符串触达(折叠仅认含换行字符串)。 */
const summaryOf = (v: unknown): string => {
  if (v === undefined || v === null) return '(空)';
  if (typeof v === 'object')
    return `${Array.isArray(v) ? '[…]' : '{…}'} ${Object.keys(v as object).length} 项`;
  if (typeof v === 'string' && isHugeValue(v))
    return `共 ${v.split('\n').length} 行`;
  return String(v);
};

/** 2026-10-13 23:55 小欧 - 空容器不配折叠箭头(`[]`/`{}` 折开无意义)。
 *  命中: `{"matches": []}`、tables[]/notes[]/images[] 条件缺失、find_command 未命中。 */
const hasEntries = (v: unknown): boolean =>
  typeof v === 'object' && v !== null && Object.keys(v as object).length > 0;

const fullTextOf = (v: unknown): string => {
  if (v === undefined || v === null) return '(空)';
  // 2026-10-13 小欧 - 对象用**紧凑单行** JSON(无 2 空格缩进): 实测 3 键对象在 12px 等宽下
  //   缩进展开要占 8 行、且把面板 fit-content 撑出大片空白; 紧凑后一行读完, 仍不折叠/不截断,
  //   超宽照常折行(规则不变)
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};

/** DC-16: 浮层复制为 key=value 逐行(非 JSON), 面向人工核对/贴工单 */
const toKeyValueText = (params: Record<string, unknown>): string =>
  Object.entries(params)
    // 非巨型值复制**完整内容**(小对象给 JSON, 长字符串给全文), 巨型值给紧凑摘要「共 N 行」
    .map(([k, v]) => `${k} = ${isHugeValue(v) ? summaryOf(v) : fullTextOf(v)}`)
    .join('\n');

// ==================== 结果视图(文档[29] §6.3/§6.2.4) ====================

/** 2026-10-13 23:00 小欧 - 值渲染模式(依赖注入, OCP): 'param'(默认)= 现有参数视图, 渲染路径与
 *  样式逐像素不变(规格表样式不许改变); 'result' = 结果视图(对象/数组可折叠 + 缩进 JSON + diff 着色)。 */
/**
 * 结果视图的**递归嵌套渲染**(§6.3, 2026-10-14 小欧 - 北京老陈裁定; 独立组件 SRP)。
 *
 * 病根: 递归结构(`tree.children` / `get_db_schema.tables[].columns[]` / `read_xlsx.sheets[]`)
 *   原用 `JSON.stringify(v, null, 2)` **整块展开** —— 缩进随深度累积, 3 层目录即缩进 8~12 格,
 *   在 720px 面板内触发折行变成"斜坡", 层级不可辨, 且行数暴涨要滚很久。
 *
 * 修法: 容器**逐层独立折叠**, 默认全折叠, 按需展开; 标量叶子直显。
 *
 * 规则(KISS, **无任何启发式**):
 *   - 对象按 key 出行; 数组按**下标**出行(北京老陈选 A 方案)
 *   - 每个非空容器一个折叠行, 摘要复用 `summaryOf`(`[…]` / `{…}` / `共 N 行`)
 *   - 多行字符串沿用既有「共 N 行 + ValuePre 全显」
 *   - **不做**「数组元素全是对象就跳过下标层」这类特判 —— 那要猜哪列是标题, 会引入错误
 *
 * 仅 `valueMode='result'` 使用; **参数视图零影响**(规格表一行代码未动)。
 */
const NESTED_INDENT_PX = 12;

const NestedRow: React.FC<{ label: string; value: unknown; depth: number }> = ({
  label,
  value,
  depth,
}) => {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((p) => !p);
  const isContainer = hasEntries(value);
  const isMultiline = isHugeValue(value);
  const rowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: Spacing.SM,
    lineHeight: `${FontSize.CODE + Spacing.XS}px`,
    paddingLeft: depth * NESTED_INDENT_PX,
  };
  const keyStyle: React.CSSProperties = {
    width: 140,
    flexShrink: 0,
    fontFamily: FontFamily.MONO,
    fontSize: FontSize.CODE,
    color: Colors.TEXT.SECONDARY,
    wordBreak: 'break-word',
  };
  // 叶子(标量 / 空容器): 直显, 无箭头
  if (!isContainer && !isMultiline) {
    return (
      <div style={rowStyle}>
        <span style={keyStyle}>{label}</span>
        <PlainValue value={value} valueMode="result" />
      </div>
    );
  }
  return (
    <>
      {/* 只复用 ValueToggle 的交互, **不在行级再加 onClick/role/tabIndex** ——
          ValueToggle 已自带 onClick + role=button + tabIndex(L492-499), 行级再套一套会
          ①双触发(开→立刻关) ②产生嵌套 button(a11y 违规)。故可点区仅箭头+摘要, 与规格表一致。 */}
      <div style={rowStyle}>
        <ValueToggle value={value} open={open} onToggle={toggle} />
        <span style={keyStyle}>{label}</span>
      </div>
      {open &&
        (isContainer ? (
          <NestedRows value={value} depth={depth + 1} />
        ) : (
          <ValuePre value={value} valueMode="result" />
        ))}
    </>
  );
};

/** 2026-10-14 小欧 - 嵌套行集合: 对象按 key / 数组按下标(A 方案)。
 *  特判: 数组元素**全是对象**时**不套一层可折叠**, 下标降为不可点的分组标题, 直接列出该元素的 key。
 *  动机: `tree.children` / `read_xlsx.sheets[]` / `get_db_schema.tables[]` 全是这个形态 ——
 *  若给每个元素再加一层折叠, 用户要展开"父容器→下标→字段"三次点击才看到一个目录名, 反而更难读。
 *  该判断是**纯结构判断**(不猜哪列是标题), 故不会引入错误。 */
const isAllObjectArray = (v: unknown[]): boolean =>
  v.length > 0 &&
  v.every((x) => typeof x === 'object' && x !== null && !Array.isArray(x));

const NestedRows: React.FC<{ value: unknown; depth: number }> = ({
  value,
  depth,
}) => {
  const indexHeaderStyle: React.CSSProperties = {
    paddingLeft: depth * NESTED_INDENT_PX,
    lineHeight: `${FontSize.CODE + Spacing.XS}px`,
    fontFamily: FontFamily.MONO,
    fontSize: FontSize.CODE,
    color: Colors.TEXT.TERTIARY,
  };
  if (Array.isArray(value)) {
    const arr = value as unknown[];
    if (isAllObjectArray(arr)) {
      return (
        <div>
          {arr.map((el, i) => (
            <div key={i}>
              <div style={indexHeaderStyle}>{i}</div>
              <NestedRows
                value={el as Record<string, unknown>}
                depth={depth + 1}
              />
            </div>
          ))}
        </div>
      );
    }
    return (
      <div>
        {arr.map((v, i) => (
          <NestedRow key={i} label={String(i)} value={v} depth={depth} />
        ))}
      </div>
    );
  }
  const rows = Object.entries(value as Record<string, unknown>);
  return (
    <div>
      {rows.map(([label, v]) => (
        <NestedRow key={label} label={label} value={v} depth={depth} />
      ))}
    </div>
  );
};

export type ValueMode = 'param' | 'result';

/** 折叠判定: 参数模式 = 原 isHugeValue(零变化); 结果模式额外让非空对象/数组可折叠(§6.4.3)。 */
const isFoldable = (v: unknown, mode: ValueMode): boolean =>
  isHugeValue(v) || (mode === 'result' && hasEntries(v));

/** 2026-10-13 23:00 小欧 - 唯一不渲染的字段: `read_media_file.base64_data`(MB 级 base64, 纯体积原因)。
 *  该工具的有效信息(file_name + mime_type)已在同表另两行给出。 */
const RESULT_HIDDEN_KEYS: ReadonlySet<string> = new Set(['base64_data']);
/**
 * 2026-10-14 小欧 - 可见条目 + **非 dict 防御**。
 *
 * ①防御的必要性(类型防御, 不是"兜底"): 结果视图按「顶层是对象」设计, 但 67 个工具的 data 形态
 *   由后端决定, 不能只凭文档断言。实测两条独立证据均未发现非 dict —— AST 扫 453 个
 *   `build_*(data=)` 传入点, 非 dict 字面量 0 个; 真实运行数据 759 条 `原始内容.data` 全为 dict。
 *   仍保留防御: 万一出现 str, `Object.entries("abc")` 会渲染成「0→a / 1→b / 2→c」的字符表;
 *   出现 list 会渲染成「下标→值」—— 两者都是**误导**, 降级为无条目走空态提示。
 *   注: §6.1.3「不兜底」指的是**不回退到 params/data_text**, 与本处的类型防御不冲突。
 *
 * ②只过滤 `base64_data`(体积原因)。下划线键**全放行** —— 见 §6.2.4.1 撤销说明。
 */
const visibleResultEntries = (result: unknown): Array<[string, unknown]> =>
  result !== null && typeof result === 'object' && !Array.isArray(result)
    ? Object.entries(result as Record<string, unknown>).filter(
        ([k]) => !RESULT_HIDDEN_KEYS.has(k)
      )
    : [];

/** 2026-10-13 23:00 小欧 - 结果视图取值: 对象/数组用缩进 JSON(含换行才可折叠, 紧凑单行不可折叠)。
 *  不改共享 `fullTextOf`(北京老陈方案 B), 故参数视图零影响。 */
const resultTextOf = (v: unknown): string => {
  // 2026-10-13 23:55 小欧 - 空串也给 `(空)`: 否则规格表出现视觉空洞, 用户分不清「本来没有」
  //  还是「渲染漏了」。命中 stderr(常态空)与各工具 truncated_reason(未截断时为 '')。
  if (v === undefined || v === null || v === '') return '(空)';
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      // 环引用: 退回紧凑串, 绝不因渲染抛异常(会白屏整棵流水线)
      return String(v);
    }
  }
  return String(v);
};

/**
 * 2026-10-14 小欧 - 北京老陈裁定: **默认 = `TOOL结果`, 但三个标签都记忆**。
 *
 * 语义(前几轮反复读错, 此处定死):
 *   - 无有效记忆时(首次 / 脏值) → 落在 `result`(`TOOL结果` 即**默认标签**);
 *   - 用户切到 `分组参数`/`规格表参数`/`TOOL结果` **任一个都写入**并沿用 —— 即"切到 TOOL结果 也记住";
 *   - 故刷新后仍是用户最后选择的那个, 不会莫名跳回默认。
 *
 * 先前「不记忆 result」的理由(20 个工具 raw_data 为 {} 会落空白页)**已不成立**:
 * 空态现显示「本次工具执行：<summary>」(见 render 分支), 是如实说明而非空白。
 */
const VIEW_LS_KEY = 'step.params.view';
/**
 * 2026-10-14 小欧 - 一次性迁移标记。
 * 起因: 默认标签由「分组参数」改为「TOOL结果」后, **旧方案遗留的 localStorage 值会污染新默认** ——
 * 用户此前点过「规格表参数」, 存下 `'spec'`, 升级后打开仍落在规格表, 看起来像"默认没生效"。
 * 故首次加载清一次旧值并打版本标记, 之后按新语义(默认 result + 三者都记忆)正常工作。
 * 只清一次: 标记存在后不再清, 用户的正常选择不会被抹掉。
 */
const VIEW_LS_VER_KEY = 'step.params.view.ver2';

const readView = (): ParamsView => {
  try {
    if (!window.localStorage.getItem(VIEW_LS_VER_KEY)) {
      window.localStorage.removeItem(VIEW_LS_KEY);
      window.localStorage.setItem(VIEW_LS_VER_KEY, '2');
    }
    const v = window.localStorage.getItem(VIEW_LS_KEY);
    return v === 'spec' || v === 'group' || v === 'result' ? v : 'result';
  } catch {
    return 'result';
  }
};

// ==================== 巨型值(两视图共用) ====================

/** 折叠切换行(两视图共用): CircleArrow(14,PRIMARY) + 「共N行·展开/收起」, 不用裸 ▸/▾(T29) */
const ValueToggle: React.FC<{
  value: unknown;
  open: boolean;
  onToggle: () => void;
}> = ({ value, open, onToggle }) => {
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onToggle();
    }
  };
  return (
    <span
      // 2026-10-13 三堂会审 A2: 与树节点、✕ 共用 .params-clickable, 补齐 V8「按钮也要 hover/focus 反馈」
      className="params-clickable"
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onClick={onToggle}
      onKeyDown={onKeyDown}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Spacing.SM,
        cursor: 'pointer',
        color: Colors.PRIMARY,
        fontSize: FontSize.CODE,
        fontFamily: FontFamily.MONO,
        // 规格表里本行是 flex item, flex:1 让折叠行占满剩余宽度; 分组视图里父为块级 span, 此值无副作用
        flex: 1,
        minWidth: 0,
      }}
    >
      <CircleArrow
        size={14}
        color={Colors.PRIMARY}
        expanded={open}
        animated={false}
      />
      {open ? '收起' : `${summaryOf(value)} · 展开`}
    </span>
  );
};

/** 2026-10-13 23:00 小欧 - diff 行级着色(§6.6): `@@`蓝 / `+`绿 / `-`红 / 其他走代码块前景色。
 *  逐行套 span, 不用 HTML 注入 —— React 文本节点天然转义, 无 XSS 风险。 */
const diffLineColor = (line: string): string | undefined => {
  if (line.startsWith('@@')) return Colors.PRIMARY;
  if (line.startsWith('+')) return Colors.SUCCESS;
  // 2026-10-13 23:40 小欧 - `-` 用 ERROR(红) 而非 ORANGE_RED: 后者是"未执行/超时警示"橙,
  // 色相与语义都不符, 违背规格「`-` 红」。
  if (line.startsWith('-')) return Colors.ERROR;
  return undefined; // 上下文行: 用代码块自身前景色, 不覆盖
};

const DiffPre: React.FC<{ text: string }> = ({ text }) => (
  <>
    {text.split('\n').map((line, i) => {
      const color = diffLineColor(line);
      return (
        <span key={i} style={color ? { color } : undefined}>
          {line}
          {i < text.split('\n').length - 1 ? '\n' : ''}
        </span>
      );
    })}
  </>
);

/**
 * 巨型值展开体(两视图共用): <pre> 显示**全部行数**。
 * 2026-10-13 小欧 - 北京老陈裁定「严禁限制行数, 有多少行显示多少行」:
 *   初稿在此加了 maxHeight: Size.PARAMS_PANEL_MAX_H(240) + overflowY:auto(限高滚动),
 *   属于截断式隐藏, 已删。底/框/圆角与 MarkdownText 代码块同款(T32)。
 * 2026-10-13 23:00 小欧 - 文档[29]§6.4.3/§6.6: 增可选 valueMode。
 *   默认 'param' 时文本取 fullTextOf、容器样式逐像素不变(北京老陈明令规格表样式不许改变);
 *   'result' 时取 resultTextOf(缩进 JSON, 使对象/数组可折叠), 且值为 diff 字符串时逐行着色。
 */
/** 2026-10-13 23:40 小欧 - 判据是**字段名**而非"含换行": 否则 stdout/content 等普通多行文本
 *  的行首 `+`/`-` 会被误染(§6.6 只要求 raw_data.diff 着色)。 */
const isDiffKey = (k: string): boolean =>
  k === 'diff' || k.endsWith('_diff') || k.endsWith('Diff');

const ValuePre: React.FC<{
  value: unknown;
  valueMode?: ValueMode;
  /** 结果模式字段名: 仅 diff 字段做行级增删着色 */
  keyName?: string;
}> = ({ value, valueMode = 'param', keyName }) => {
  const isResult = valueMode === 'result';
  const text = isResult ? resultTextOf(value) : fullTextOf(value);
  // 仅结果模式对 diff 键着色; 参数视图的 diff 参数不着色(§6.6 约束)
  const asDiff =
    isResult &&
    typeof value === 'string' &&
    keyName !== undefined &&
    isDiffKey(keyName);
  /**
   * 2026-10-14 小欧 - 结果模式: **容器**走 `NestedRows` 递归折叠(不塌成整块缩进 JSON),
   * 标量/字符串仍走原 `<pre>`。判据 = 该值是否为非空容器(`hasEntries`), 无字段名特判。
   */
  if (isResult && hasEntries(value)) {
    return (
      <div style={{ flexBasis: '100%', width: '100%' }}>
        <NestedRows value={value} depth={0} />
      </div>
    );
  }
  return (
    <pre
      style={{
        margin: `${Spacing.SM}px 0 0`, // 2026-10-13 小欧 - 与上方折叠行拉开间距(原 4px, 代码块贴得太近)
        padding: Spacing.SM,
        background: Colors.BG.SECONDARY,
        border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: Radius.SM,
        fontFamily: FontFamily.MONO,
        fontSize: FontSize.CODE,
        lineHeight: `${FontSize.CODE + Spacing.XS}px`,
        color: Colors.TEXT.STRONG,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        // 规格表「巨型值整宽跨行」(§3.5.3): 父行是 flexWrap 容器,
        //   flexBasis:100% 让本块换行独占一整行(不再挤在右侧值列里)
        flexBasis: '100%',
        width: '100%',
      }}
    >
      {asDiff ? <DiffPre text={text} /> : text}
    </pre>
  );
};

/**
 * 普通值: 等宽/字号显式声明不靠根继承(A1) + **完整展示不折叠**(2026-10-13 北京老陈裁定)
 *   内容取 `fullTextOf` —— 对象直接给格式化 JSON(不再显示 `{…} N 项` 摘要、更不给折叠箭头),
 *   长单行字符串折行显示全部字符, 空值给 `(空)` 占位。
 */
const PlainValue: React.FC<{ value: unknown; valueMode?: ValueMode }> = ({
  value,
  valueMode = 'param',
}) => (
  <span
    style={{
      // 2026-10-13 小欧 - 空值用更浅的 TERTIARY: 「(空)」是"没有值", 与真实值(PRIMARY)同色会
      //   和 false/0 混淆(实测二者原本同为灰色); 拉浅一档后一眼可辨
      color:
        value === undefined ||
        value === null ||
        (valueMode === 'result' && value === '')
          ? Colors.TEXT.TERTIARY
          : Colors.TEXT.PRIMARY,
      fontFamily: FontFamily.MONO,
      fontSize: FontSize.CODE,
      display: 'inline-block',
      maxWidth: '100%',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      flex: 1,
      minWidth: 0,
    }}
  >
    {/* 2026-10-13 23:55 小欧 - RC4: 结果模式走 resultTextOf(空串给「(空)」), 参数模式走 fullTextOf。
        结果模式下不会有对象落到这里(对象必可折叠 → 走 ValuePre), 故 RC2/RC3 的容器逻辑不受影响 */}
    {valueMode === 'result' ? resultTextOf(value) : fullTextOf(value)}
  </span>
);

/**
 * 分组视图用的值渲染: 巨型值在**值列内**竖排展开。
 * 2026-10-13 小欧 - §3.5.3 要求规格表里巨型值「整宽跨行成代码块」, 而 React 无法把 pre 提到
 *   父级行容器之外, 故这里用 <div> 包裹让 pre 留在本列内(分组视图不要求跨行),
 *   规格表改走自己的「行 + 整宽 pre」两段结构, 三块(ValueToggle/ValuePre/PlainValue)共用不重复(DRY)
 */
const ParamValue: React.FC<{ value: unknown }> = ({ value }) => {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((p) => !p);
  if (!isHugeValue(value)) return <PlainValue value={value} />;
  return (
    <div>
      <ValueToggle value={value} open={open} onToggle={toggle} />
      {open && <ValuePre value={value} />}
    </div>
  );
};

// ==================== 乙 · 分组卡片(默认) ====================

const GroupView: React.FC<{ params: Record<string, unknown> }> = ({
  params,
}) => {
  const buckets = useMemo(() => {
    const map = new Map<Category, Array<[string, unknown]>>();
    CATEGORY_META.forEach((c) => map.set(c.id, []));
    Object.entries(params).forEach(([k, v]) => {
      const bucket = map.get(categorize(k, v));
      if (bucket) bucket.push([k, v]);
    });
    return map;
  }, [params]);

  return (
    <div>
      {CATEGORY_META.map((c) => {
        const rows = buckets.get(c.id) ?? [];
        if (rows.length === 0) return null; // 空类不渲染(§3.5.2)
        return (
          <div key={c.id} style={{ marginTop: Spacing.SM }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: Spacing.SM,
              }}
            >
              <span
                style={{
                  width: 2,
                  height: 10,
                  borderRadius: 1,
                  background: c.color,
                }}
              />
              <span
                style={{
                  fontSize: FontSize.CODE,
                  color: Colors.TEXT.SECONDARY,
                }}
              >
                {c.label}
              </span>
            </div>
            <div style={{ marginLeft: Spacing.SM, marginTop: Spacing.XS }}>
              {rows.map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: Spacing.SM,
                    marginTop: Spacing.XS - 2,
                  }}
                >
                  <span
                    style={{
                      width: 96, // 布局常量: 分组视图 key 列定宽, 保证值列起始 x 对齐
                      flexShrink: 0,
                      fontFamily: FontFamily.MONO,
                      fontSize: FontSize.CODE,
                      color: Colors.TEXT.SECONDARY,
                      // 2026-10-13 小欧 - 八轮核查: key 列原为 break-all, 与 §2.5 V3「break-all → break-word」
                      //   及 T13「非 break-all」冲突(值列已改、key 列漏改), 此处统一 break-word
                      wordBreak: 'break-word',
                    }}
                  >
                    {k}
                  </span>
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontFamily: FontFamily.MONO,
                      fontSize: FontSize.CODE,
                      wordBreak: 'break-word',
                    }}
                  >
                    <ParamValue value={v} />
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ==================== 甲 · 规格表 ====================

/**
 * 甲 · 规格表: 固定两列(key 140px 左对齐 / 值 flex:1), 行间 1px BORDER.LIGHT 分割线;
 * **巨型值整宽跨行成代码块**(§3.5.3) —— 靠行容器 flexWrap + ValuePre 的 flexBasis:100% 实现。
 * 2026-10-13 小欧: 展开态按 key 记在 Set 里(与 ParamsTree 同范式), 不用布尔数组(删除/新增无需对齐下标)
 */
const SpecView: React.FC<{
  params: Record<string, unknown>;
  valueMode?: ValueMode;
}> = ({ params, valueMode = 'param' }) => {
  const [openKeys, setOpenKeys] = useState<ReadonlySet<string>>(
    () => new Set()
  );
  const toggle = (k: string) =>
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  return (
    <div>
      {Object.entries(params).map(([k, v]) => {
        // 2026-10-13 23:00 小欧 - 文档[29]§6.4.3: 折叠判定随模式变化(结果模式含对象/数组)
        const huge = isFoldable(v, valueMode);
        const open = huge && openKeys.has(k);
        return (
          <div
            key={k}
            style={{
              display: 'flex',
              flexWrap: 'wrap', // 巨型值代码块借此换行独占整宽
              alignItems: 'flex-start',
              gap: Spacing.SM,
              paddingTop: Spacing.XS,
              paddingBottom: Spacing.XS,
              borderBottom: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
            }}
          >
            <span
              style={{
                width: 140, // 布局常量: 规格表 key 列定宽(§3.5.3), **左对齐**
                flexShrink: 0,
                // 2026-10-13 小欧 - 十二轮自查订正: 原写 textAlign:'right' 是照 §3.5.3 的"右对齐"文字,
                //   但那与 §2.3 规格表示意图(第 298-303 行, key 从同一左缘起)**自相矛盾**, 且与
                //   GroupView 的 key 列(96px, 未设对齐即左对齐)口径不一 —— 两视图统一左对齐。
                //   key-value 表右对齐只适用于数字列; 等宽字体下长短 key 右对齐会让扫读起点参差
                fontFamily: FontFamily.MONO,
                fontSize: FontSize.CODE,
                color: Colors.TEXT.SECONDARY,
                // 2026-10-13 小欧 - 八轮核查: 同 GroupView key 列, 统一 break-word(V3/T13)
                wordBreak: 'break-word',
              }}
            >
              {k}
            </span>
            {huge ? (
              <>
                <ValueToggle value={v} open={open} onToggle={() => toggle(k)} />
                {/* 2026-10-13 23:40 小欧 - 透传字段名 k: 结果模式下只有 diff 字段才逐行增删着色(§6.6);
                    参数模式 isResult=false, keyName 不参与判定, 行为与改动前逐像素一致 */}
                {open && (
                  <ValuePre value={v} valueMode={valueMode} keyName={k} />
                )}
              </>
            ) : (
              /* 2026-10-13 23:55 小欧 - RC4: 透传 valueMode, 结果模式下空串走「(空)」占位 */
              <PlainValue value={v} valueMode={valueMode} />
            )}
          </div>
        );
      })}
    </div>
  );
};

// ==================== 面板 ====================

interface ParamsPanelProps {
  toolName: string;
  params: Record<string, unknown>;
  /** T15: ✕ / Esc / 点外面关闭; 关闭动作回交 FloatingEntry 的 onOpenChange */
  onClose: () => void;
  /**
   * 2026-10-13 23:00 小欧 - 文档[29]§6.10: 工具原始结果, 供「结果」标签渲染。
   *   OCP: 可选 prop, 既有调用方(只传 params)零影响。
   */
  result?: unknown;
  /**
   * 2026-10-14 小欧 - 北京老陈裁定: `raw_data` 为空时**不显示空白**, 改显「本次工具执行：<summary>」。
   *   取值 `llm_data.summary`(后端每条 tool_result 都带, 如"已读取 3 个文件, 2 个跳过")。
   *   ⚠️ 这**不是** §6.1.3 的「兜底」: 兜底=拿 params/data_text 冒充原始数据; 本条=承认没有原始数据,
   *   改显一句**如实**的说明, 与空白相比是信息增量而非伪装。
   */
  resultSummary?: string;
}

/**
 * ParamsPanel - 工具参数浮层面板(浮层开合/锚点/a11y/焦点管理全部由 FloatingEntry 承担,
 * 本组件只负责"渲染什么内容"与面板内样式 — SRP, 见 §3.5)
 *
 * @author 小欧
 * @since 2026-10-13
 */
const ParamsPanel: React.FC<ParamsPanelProps> = ({
  toolName,
  params,
  onClose,
  result,
  resultSummary,
}) => {
  const [view, setView] = useState<ParamsView>(readView);
  /**
   * 2026-10-14 小欧 - 三个标签**都记忆**(含 `TOOL结果`): 写入即下次沿用。
   *   默认值由 `readView` 兜底(无有效值时 `result`), 二者配合:
   *   首次打开 = TOOL结果; 之后打开 = 用户最后选择。
   */
  const onViewChange = (next: ParamsView) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_LS_KEY, next);
    } catch {
      /* 隐私模式/存储禁用: 仅本次会话生效, 不阻断 */
    }
  };
  // 2026-10-13 23:00 小欧 - 文档[29]§6.3: 结果视图过滤不渲染字段后取其余条目。
  //   ⚠️ 不兜底(铁律): result 为空/未传时 entries 为空数组,
  //   **绝不**拿 params 冒充原始数据(文档[29]§6.1.3、§6.8)
  // 2026-10-14 小欧 订正: 原注三处过期 —— ①原写「过滤 base64_data 与下划线私有键」, 下划线过滤已于 v2.12 撤销,
  //   现仅过滤 base64_data(见 RESULT_HIDDEN_KEYS); ②原写「内容区空白」, 现空态改显「本次工具执行：<summary>」
  //   (见下方空态分支); ③原写「绝不回退 params / llm_data / data_text」, 空态确取 llm_data.summary, 但那**不是**
  //   兜底(兜底=拿 params 冒充原始数据; 本条=承认无原始数据、改显如实说明, 见 resultSummary prop 注释) — 小欧-2026-10-14
  const resultEntries = useMemo(
    () => (result ? visibleResultEntries(result) : []),
    [result]
  );
  /**
   * 复制内容按视图分支(§6.10): 参数视图复制 key=value 逐行(DC-16);
   * 结果视图复制 raw_data 的缩进 JSON(不是过滤后的视图, 复制的是原始数据)。
   */
  const copyText = useMemo(() => {
    if (view !== 'result') return toKeyValueText(params);
    if (!result) return '';
    try {
      return JSON.stringify(result, null, 2);
    } catch {
      return '';
    }
  }, [view, params, result]);
  const title =
    view === 'result'
      ? `${toolName} · 结果`
      : `${toolName} · 参数 ${Object.keys(params).length} 项`;
  const onCloseKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <div
      style={{
        // 2026-10-13 小欧 - 十一轮自查**撤回**原 D-8(误判): 面板外壳**必须**自带卡片规格, 与设计
        //   §3.5.1 结构图「卡片底 = BG.SECONDARY + BORDER.DEFAULT 1px + Radius.SM 4」、DC-19、T32 三处一致。
        //   误判根源: 拿 G6/G8 的「content 不自绘外框」当依据, 但那两个 content 是纯文本/事件时间轴,
        //   而本方案的浮层内容**本身就是一张卡片** —— 两类 UI 不同, 依据套错。
        //   防「框中框」: Popover 的 12px 内边距已由 cardStyle.padding=0 归零(见 §4.6.2), 二者不叠加。
        //   根上不挂 fontFamily: 等宽只给 key/值/pre(免污染面板标题与分类标签)
        //   行高显式 16px(§2.2/§2.5 V7): antd Popover 默认 line-height 1.5714 → 12px 字会排成
        //   约 18.9px 且与 pre 的 16px 混排不齐, 故在此统一
        lineHeight: `${FontSize.CODE + Spacing.XS}px`,
        background: Colors.BG.SECONDARY,
        border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: Radius.SM,
        // 2026-10-13 小欧 - 北京老陈裁定「严禁限制行数」的正确落法:
        // 行数不裁剪, 但浮层 portal 到 body 脱离右栏滚动容器, 完全不限高则超视口内容永远够不着。
        //   故限高 + 头部固定 + 仅内容区滚动。58 = 留白32 + antd inner padding 24 + 边框2。
        display: 'flex',
        flexDirection: 'column',
        maxHeight: 'calc(100vh - 58px)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          padding: Spacing.SM,
          borderBottom: `${BorderWidth.THIN}px solid ${Colors.BORDER.DEFAULT}`,
        }}
      >
        <CodeOutlined
          // 2026-10-13 小欧 - 改为中性灰: 本图标是**装饰**(表示"代码/参数"), 不可点。
          //   系统里 PRIMARY 蓝是可交互信号(CircleArrow 折叠箭头、展开行、按钮激活态都是蓝),
          //   装饰件用蓝会让人以为能点 → 误导。装饰一律走 TEXT.SECONDARY 中性色。
          style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.CODE }}
        />
        <span
          style={{
            fontSize: FontSize.CODE,
            color: Colors.TEXT.STRONG,
            // 2026-10-13 23:20 小欧 - 北京老陈裁定: 标题行**不许换行, 不许折行**。
            //   原为 wordBreak:'break-word'(可折行), 三标签后头部固定元素变宽, 标题会被挤成两行。
            //   现改 nowrap + flexShrink:0(不压缩), 并已把 PARAMS_PANEL_MAX_W 加宽 640→720 留出空间。
            //   ⚠️ nowrap 下若标题仍超宽(超长工具名 + 极窄屏), 会溢出而非折行 ——
            //   这是"不许折行"的必然代价, 故 minWidth 同步提到 460 保证窄屏也不触发(见 Size 令牌)。
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {title}
        </span>
        <span style={{ flex: 1 }} />
        <Segmented
          size="small"
          options={VIEW_OPTIONS}
          value={view}
          onChange={(v) => onViewChange(v as ParamsView)}
        />
        {/* DC-20: 面板头用 inline 变体, 否则绝对定位会压住标题。
            2026-10-13 小欧 - 三控件基线对齐: Segmented(size=small) 高 24px, 而 CopyButton 高约 20px、
            ✕ 高约 16px, 直接并排会顶端/底端都不齐(实测截图)。统一把后两者包进同高的居中盒 */}
        <span style={HEADER_CTRL_BOX}>
          <CopyButton text={copyText} inline />
        </span>
        <span
          // 2026-10-13 三堂会审 A2: 共用 .params-clickable, 补齐 V8「按钮也要 hover/focus 反馈」
          className="params-clickable"
          role="button"
          tabIndex={0}
          aria-label="关闭参数面板"
          // 2026-10-13 18:20 小欧 - 关闭动作本组件自持, 无需止冒泡:
          //   浮层门户内容的点击外泄由 FloatingEntry 在**卡片根**统一拦截(该处是唯一真源),
          //   此处再拦一次属重复打点(DRY)。本组件只负责"点了要关"。
          onClick={onClose}
          onKeyDown={onCloseKeyDown}
          style={{
            ...HEADER_CTRL_BOX,
            cursor: 'pointer',
            color: Colors.TEXT.SECONDARY,
            fontSize: FontSize.CODE,
          }}
        >
          <CloseOutlined />
        </span>
      </div>
      <div
        style={{
          padding: Spacing.SM,
          // 仅内容区滚动, 头部(工具名/Segmented/复制/✕)常驻可见; 行数不裁剪
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
        }}
      >
        {/* 2026-10-13 23:00 小欧 - 文档[29]§6.10 三视图派发; 结果视图不兜底(§6.8)
            2026-10-14 小欧 - 北京老陈裁定改: 空态不显示空白, 显「本次工具执行：<summary>」 */}
        {view === 'result' && resultEntries.length === 0 ? (
          <div
            style={{
              padding: `${Spacing.XS}px 0`,
              fontFamily: FontFamily.MONO,
              fontSize: FontSize.CODE,
              lineHeight: `${FontSize.CODE + Spacing.XS}px`,
              color: Colors.TEXT.TERTIARY,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            本次工具执行：{resultSummary || '无结果数据'}
          </div>
        ) : view === 'group' ? (
          <GroupView params={params} />
        ) : view === 'spec' ? (
          <SpecView params={params} valueMode="param" />
        ) : (
          <SpecView
            params={Object.fromEntries(resultEntries)}
            valueMode="result"
          />
        )}
      </div>
    </div>
  );
};

export { ParamsPanel };
export default ParamsPanel;
