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
//     外壳 maxHeight:calc(100vh-32px) + 内容区滚动 —— 行数一个不裁剪, 但浮层 portal 脱离右栏滚动容器, 完全不限会超出视口不可达;
//   ⑨面板头: 分组/规格表(Segmented 24px)、复制(≈20px)、✕(≈16px) 统一包进 24px 居中盒(HEADER_CTRL_BOX)对齐基线;
//     装饰图标 </> 由 PRIMARY 蓝改 TEXT.SECONDARY 中性灰(蓝在本系统=可点, 装饰用蓝会误导), 工具名去 nowrap 改折行 — 小欧-2026-10-13
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
  Size,
  Spacing,
} from '@/utils/stepStyles';

// ==================== 模块级常量(防每次渲染重建, 同 REJECT_LABEL_MAP 范式) ====================

/** 巨型值字符阈值(判定阈值非视觉令牌, 故不入 stepStyles — §3.4.3) */
const HUGE_VALUE_CHARS = 200;

const PATH_KEYS: ReadonlySet<string> = new Set([
  'path',
  'dir_path',
  'file_path',
  'source_path',
  'dest',
  'output_path',
]);
const ENCODING_KEYS: ReadonlySet<string> = new Set(['encoding', 'charset']);

export const PARAMS_VIEW_MAP = { group: '分组', spec: '规格表' } as const;
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
];
const VIEW_LS_KEY = 'step.params.view';

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
type Category = 'payload' | 'switch' | 'path' | 'encoding' | 'other';
const CATEGORY_META: ReadonlyArray<{
  id: Category;
  label: string;
  color: string;
}> = [
  // 2026-10-13 小欧 - 十二轮自查订正:
  //   ①渲染顺序改为设计 §2.3 示意图/§3.5.2 表的 路径→开关→编码→正文载荷→其他。
  //     原顺序照搬 categorize 的**判定优先级**, 把"优先级"误当"渲染顺序", 正文载荷跑到了最前。
  //     categorize 按 id 查表, 调数组顺序**不影响分类判定**(改动零风险)。
  //   ②色条统一 BORDER.STRONG: 原 5 档中性灰在 #fafafa 面板底上, #e8e8e8/#f0f0f0 对比度仅
  //     1.1/1.05:1 等于看不见, 且开关与编码本就同档无区分。设计 §3.5.2 原文本即写"类名靠文字区分",
  //     故色条只当分组锚点、不承担分类编码。仍取自 Colors.BORDER.*(DC-21/T30 不违), 不新增颜色
  { id: 'path', label: '路径', color: Colors.BORDER.STRONG },
  { id: 'switch', label: '开关', color: Colors.BORDER.STRONG },
  { id: 'encoding', label: '编码', color: Colors.BORDER.STRONG },
  { id: 'payload', label: '正文载荷', color: Colors.BORDER.STRONG },
  { id: 'other', label: '其他', color: Colors.BORDER.STRONG },
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

/** §2.3.2 判定优先级链: 严格自上而下, 命中即止, 防一个参数落进两组 */
const categorize = (k: string, v: unknown): Category => {
  if (isPayload(v)) return 'payload';
  if (typeof v === 'boolean') return 'switch';
  if (PATH_KEYS.has(k) || (typeof v === 'string' && isPathLike(v)))
    return 'path';
  if (ENCODING_KEYS.has(k)) return 'encoding';
  return 'other';
};

const summaryOf = (v: unknown): string => {
  if (v === undefined || v === null) return '(空)';
  if (typeof v === 'object') return `{…} ${Object.keys(v as object).length} 项`;
  if (typeof v === 'string' && isHugeValue(v))
    return `共 ${v.split('\n').length} 行`;
  return String(v);
};

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

const readView = (): ParamsView => {
  try {
    return window.localStorage.getItem(VIEW_LS_KEY) === 'spec'
      ? 'spec'
      : 'group';
  } catch {
    return 'group';
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

/**
 * 巨型值展开体(两视图共用): <pre> 显示**全部行数**。
 * 2026-10-13 小欧 - 北京老陈裁定「严禁限制行数, 有多少行显示多少行」:
 *   初稿在此加了 maxHeight: Size.PARAMS_PANEL_MAX_H(240) + overflowY:auto(限高滚动),
 *   属于截断式隐藏, 已删。底/框/圆角与 MarkdownText 代码块同款(T32)。
 */
const ValuePre: React.FC<{ value: unknown }> = ({ value }) => (
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
    {fullTextOf(value)}
  </pre>
);

/**
 * 普通值: 等宽/字号显式声明不靠根继承(A1) + **完整展示不折叠**(2026-10-13 北京老陈裁定)
 *   内容取 `fullTextOf` —— 对象直接给格式化 JSON(不再显示 `{…} N 项` 摘要、更不给折叠箭头),
 *   长单行字符串折行显示全部字符, 空值给 `(空)` 占位。
 */
const PlainValue: React.FC<{ value: unknown }> = ({ value }) => (
  <span
    style={{
      // 2026-10-13 小欧 - 空值用更浅的 TERTIARY: 「(空)」是"没有值", 与真实值(PRIMARY)同色会
      //   和 false/0 混淆(实测二者原本同为灰色); 拉浅一档后一眼可辨
      color:
        value === undefined || value === null
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
    {fullTextOf(value)}
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
const SpecView: React.FC<{ params: Record<string, unknown> }> = ({
  params,
}) => {
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
        const huge = isHugeValue(v);
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
                {open && <ValuePre value={v} />}
              </>
            ) : (
              <PlainValue value={v} />
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
}) => {
  const [view, setView] = useState<ParamsView>(readView);
  const onViewChange = (next: ParamsView) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_LS_KEY, next);
    } catch {
      /* 隐私模式/存储禁用: 仅本次会话生效, 不阻断 */
    }
  };
  const copyText = useMemo(() => toKeyValueText(params), [params]);
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
        //   行数**一个不裁剪**(各值不再有 maxHeight), 但浮层是 portal 到 body、脱离右栏滚动容器,
        //   若完全不设限, 超视口的内容既无内部滚动也无外部滚动可到达 = 永远看不到(比限高更糟)。
        //   故: 外壳限在视口内 + 头部固定 + 仅内容区滚动 —— 行数完整, 且能滚到全部。
        display: 'flex',
        flexDirection: 'column',
        maxHeight: 'calc(100vh - 32px)',
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
            // 不设 nowrap: 工具名很长时折行完整显示, 与全局「不许截断」口径一致
            wordBreak: 'break-word',
          }}
        >
          {toolName} · 参数 {Object.keys(params).length} 项
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
        {view === 'group' ? (
          <GroupView params={params} />
        ) : (
          <SpecView params={params} />
        )}
      </div>
    </div>
  );
};

export { ParamsPanel };
export default ParamsPanel;
