// 编辑历史: 2026-10-05 小欧 - 新增: thought 思考段 Markdown 渲染器(文档[9] §4.1 参考代码落地, v3.7)
//   未闭合围栏尾段按纯文本渲染(避免空 <pre> 容器凭空出现致页面位移), 其余按 Markdown 渲染 — 小欧-2026-10-05
//   v2.1 自审整改(随参考代码一并落地): ①全部自定义组件显式剥 node 防泄漏到 DOM(react-markdown v9
//   必传 node, …rest 透传即非法属性, 禁止); ②remark-breaks 保留单换行(与 pre-wrap 现有效果一致);
//   ③schema 补 input 标签+属性(GFM 任务列表复选框否则被净化剥掉); ④标题保留语义标签只压样式;
//   ⑤切分与渲染按 text useMemo(防长推理×高频 chunk 重复全量解析) — 小欧-2026-10-05
//   v3.7 小欧 落地订正(与文档 §4.1 参考代码的两处偏差, 均因参考代码自身笔误/未跑过编译):
//     ①参考代码每个组件写成 ({ node, children }: any) 后又解构 `const { node, children } = p;`
//        —— `p` 未定义, 直接抄会 ReferenceError; 改为统一 (props: MdProps) + 解构 props。
//     ②参考代码 SANITIZE_SCHEMA 用 `...(defaultSchema.tagNames ?? [])` 兜空, 实测 defaultSchema.tagNames
//        恒为数组; 保留 ?? 兜底无副作用, 不改。
//     ③参考代码未用 FontFamily.MONO 令牌而是硬编码 'Consolas, Monaco, "Courier New", monospace',
//        与本仓 stepStyles 令牌化铁律(§10 复用优先)冲突 —— 改走 FontFamily.MONO 单一真相源。
//   v3.8 小欧 三堂会审3遍后修 4 项(P4 明确不修, 理由随附):
//     ①P1 真缺陷: pre 被覆盖成 <>{children}</> + code 靠 className 猜"是否围栏" —— 无语言围栏
//       (info string 为空时 hast 无 className)整段退化成行内 code, pre 数=0、块级样式全丢。
//       改法按语义归位: pre 管块级容器, code 管行内样式, 不加依赖不加插件不留分支。
//     ②P2 闭围栏长度未校验: 补 CommonMark 规则(闭围栏长度 >= 开围栏长度), 5 行内。
//     ③P3 wordBreak 与 overflow 语义抵消: 北京老陈裁定二选一, 选**横向滚动**(删折行)。
//     ④P4 `2*3*4` 渲染成 2<em>3</em>4: **不修**。这是 CommonMark 标准行为(单星号内不为空即成斜体),
//       旧自研版为防它写的正则属非标准 hack; 修它需再引 remark 插件自造偏离标准的行为, 违
//       "不自造轮子/KISS"且徒增维护面。如实回归标准并在此登记, 便于日后有人再问时有据可查。
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import {
  Colors,
  FontSize,
  FontWeight,
  Spacing,
  BorderWidth,
  FontFamily,
} from '@/utils/stepStyles';

/**
 * react-markdown v9 传给自定义组件的 props: 必含 node(hast 节点), 一律显式剥掉不得透传(§3.5 缺陷 1)。
 */
interface MdProps {
  node?: unknown;
  children?: React.ReactNode;
  /** 围栏语言标记 language-js(渲染 code 块必需) */
  className?: string;
  href?: string;
  type?: string;
  checked?: boolean;
}

// XSS 净化配置: 默认 schema(GitHub 风格, 天然覆盖 GFM 表格/删除线)之上只补两处缺口——
//   ① code[className]: 围栏语言标记(language-js)渲染所需, 默认被剥离(剥掉则无法区分围栏/行内代码)
//   ② input 标签 + type/checked/disabled: GFM 任务列表复选框所需, 默认整个标签被剥离
// 注意: 不补 a[target/rel]——外链属性由本文件 a 组件硬编码渲染(不从 hast 取), schema 无需放行
const SANITIZE_SCHEMA = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), 'input'],
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), 'className'],
    input: ['type', 'checked', 'disabled'],
  },
};

// 代码块容器: 显式覆盖父级 whiteSpace:pre-wrap(否则 <pre> 内换行被软化) + 限高滚动
//   2026-10-05 小欧 P3 二选一(北京老陈裁定): 选**横向滚动** —— 删 wordBreak:'break-word'。
//   原同时写 wordBreak 与 overflow 两者语义抵消(折行后永不出滚动条), 二者只能留一。
//   选滚动理由: 代码块按代码语义应保列对齐, 折行破坏缩进层级; 且与 GitHub/CommonMark 生态一致。
//   wordBreak 显式写 normal 而非删净 —— 不依赖祖先继承, 意图可读且防上游将来改 getStreamStyle 串味。
const codeBlockStyle: React.CSSProperties = {
  margin: `${Spacing.XS}px 0 ${Spacing.SM}px`,
  padding: `${Spacing.XS}px ${Spacing.SM}px`,
  borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
  background: 'transparent',
  fontSize: FontSize.CODE,
  fontStyle: 'normal',
  fontFamily: FontFamily.MONO,
  whiteSpace: 'pre',
  wordBreak: 'normal',
  maxHeight: 400,
  overflow: 'auto',
  borderRadius: 0,
};

// 行内代码: 加浅底以与正文区分(不加背景色块, 与项目"内容即容器"风格一致)
const inlineCodeStyle: React.CSSProperties = {
  padding: '0 3px',
  fontSize: FontSize.CODE,
  fontStyle: 'normal',
  fontFamily: FontFamily.MONO,
  color: Colors.TEXT.STRONG,
};

const H1: React.CSSProperties = {
  fontSize: FontSize.PRIMARY,
  fontWeight: FontWeight.BOLD,
  color: Colors.TEXT.STRONG,
  margin: `${Spacing.SM}px 0 ${Spacing.XS}px`,
  lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
};
const H2 = H1;
const H3: React.CSSProperties = {
  fontSize: FontSize.SECONDARY,
  fontWeight: FontWeight.MEDIUM,
  color: Colors.TEXT.STRONG,
  margin: `${Spacing.XS}px 0`,
  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
};
const H4 = H3;
const H5: React.CSSProperties = {
  fontSize: FontSize.SECONDARY,
  fontWeight: FontWeight.REGULAR,
  color: Colors.TEXT.SECONDARY,
  margin: `${Spacing.XS}px 0`,
  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
};
const H6: React.CSSProperties = {
  fontSize: FontSize.TERTIARY,
  fontWeight: FontWeight.REGULAR,
  color: Colors.TEXT.SECONDARY,
  margin: `${Spacing.XS}px 0`,
  lineHeight: `${FontSize.TERTIARY + Spacing.XS}px`,
};
const PARA: React.CSSProperties = {
  margin: `${Spacing.XS}px 0`,
  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
};
const LIST: React.CSSProperties = {
  margin: `${Spacing.XS}px 0`,
  paddingLeft: Spacing.XL,
  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
};
const LI: React.CSSProperties = {
  margin: 0,
  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
};

// Markdown 元素样式映射: 全部走 stepStyles 既有令牌, 零硬编码颜色 — 小欧-2026-10-05
// 规则: 所有组件必须显式丢弃 node(§3.5 缺陷 1), 禁止 ...rest 透传到 DOM
// 标题保留语义标签 h1..h6(a11y 大纲不断), 只统一样式压小(§3.5 遗漏 4)
const mdComponents = {
  h1: (props: MdProps) => <h1 style={H1}>{props.children}</h1>,
  h2: (props: MdProps) => <h2 style={H2}>{props.children}</h2>,
  h3: (props: MdProps) => <h3 style={H3}>{props.children}</h3>,
  h4: (props: MdProps) => <h4 style={H4}>{props.children}</h4>,
  h5: (props: MdProps) => <h5 style={H5}>{props.children}</h5>,
  h6: (props: MdProps) => <h6 style={H6}>{props.children}</h6>,
  p: (props: MdProps) => <p style={PARA}>{props.children}</p>,
  ul: (props: MdProps) => <ul style={LIST}>{props.children}</ul>,
  ol: (props: MdProps) => <ol style={LIST}>{props.children}</ol>,
  li: (props: MdProps) => <li style={LI}>{props.children}</li>,
  blockquote: (props: MdProps) => (
    <blockquote
      style={{
        margin: `${Spacing.XS}px 0`,
        paddingLeft: Spacing.MD,
        borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
        color: Colors.TEXT.SECONDARY,
      }}
    >
      {props.children}
    </blockquote>
  ),
  hr: () => (
    <hr
      style={{
        border: 'none',
        borderTop: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
        margin: `${Spacing.SM}px 0`,
      }}
    />
  ),
  // className 原样透传: 围栏语言标记(language-js)是 react-markdown 挂在 code 节点上的唯一可观测
  //   信息(设计 §4.1 要求保留, SANITIZE_SCHEMA 亦为它放行 className), 丢了就只剩肉眼看不出区别的
  //   两种代码块; 行内代码 hast 上无此属性, React 自动省略该属性, 无需条件分支。
  code: (props: MdProps) => (
    <code className={props.className} style={inlineCodeStyle}>
      {props.children}
    </code>
  ),
  // pre 块级容器: 直接渲染, 由本组件负责块级样式。
  // 2026-10-05 小欧 P1 修复(原实现把 pre 覆盖成 <>{children}</> 让 code 组件自行产 pre, 靠 className
  //   判断"是否围栏"): react-markdown v9 中 **info string 为空时 hast 的 code 节点没有 className**,
  //   故 ```\\nplain\\n``` 这类无语言围栏被误判为行内代码, 且 pre 覆盖又把块级容器一并抹掉 →
  //   实测 pre 数=0, 多行代码挤成一行内联、换行压平、左线/限高/等宽块样式全丢(thought 贴代码极常见)。
  // 现按语义归位: pre = 块级容器(本组件), code = 行内样式(不论在不在 pre 内, 前者字体/换行由 pre 管) — 小欧-2026-10-05
  pre: (props: MdProps) => <pre style={codeBlockStyle}>{props.children}</pre>,
  a: (props: MdProps) => (
    <a
      href={props.href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        color: Colors.PRIMARY,
        textDecoration: 'underline',
        wordBreak: 'break-all',
      }}
    >
      {props.children}
    </a>
  ),
  table: (props: MdProps) => (
    <div style={{ overflowX: 'auto', margin: `${Spacing.XS}px 0` }}>
      <table
        style={{
          borderCollapse: 'collapse',
          width: '100%',
          fontSize: FontSize.SECONDARY,
        }}
      >
        {props.children}
      </table>
    </div>
  ),
  thead: (props: MdProps) => (
    <thead style={{ background: Colors.BG.TERTIARY }}>{props.children}</thead>
  ),
  th: (props: MdProps) => (
    <th
      style={{
        border: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
        padding: `${Spacing.XS}px ${Spacing.SM}px`,
        textAlign: 'left',
        fontWeight: FontWeight.MEDIUM,
        color: Colors.TEXT.STRONG,
      }}
    >
      {props.children}
    </th>
  ),
  td: (props: MdProps) => (
    <td
      style={{
        border: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
        padding: `${Spacing.XS}px ${Spacing.SM}px`,
        color: Colors.TEXT.PRIMARY,
      }}
    >
      {props.children}
    </td>
  ),
  // GFM 任务列表复选框: 只读展示。
  // ⚠️ 绝不能 `const { node, ...safe } = props` 再 {...safe} —— safe 里含 children,
  //   透传给 <input> 会抛 "input is a void element tag and must neither have children" 直接崩。
  //   故与其它组件同款: 显式丢弃 node + children, 只取白名单属性。
  input: (props: MdProps) => (
    <input
      type={props.type as 'checkbox' | undefined}
      defaultChecked={props.checked}
      disabled
      readOnly
      style={{ marginRight: Spacing.XS }}
    />
  ),
};

/**
 * 切分未闭合围栏尾段: 打字机逐字喂入时 ``` 刚出头就成立, 直接渲染会凭空产一个空的 <pre>
 * 容器造成页面位移, 且尾段代码会被当成正文吞进 pre。返回 { closedPart: 可按 Markdown 渲染的前缀,
 * openTail: 未闭合尾段(按纯文本渲染) }。
 * 纯函数 15 行, 实时/历史同一规则通吃(§3.3 已实测)。
 */
export const findUnclosedFenceTail = (
  text: string
): { closedPart: string; openTail: string } => {
  const lines = text.split('\n');
  let openIdx = -1;
  let openMark = '';
  // 2026-10-05 小欧 P2 修复(CommonMark 正确性): 原实现只比首字符(反引号 vs 波浪号), 不校验长度 ——
  //   4 反引号开围栏、3 反引号闭围栏会被误判为闭合(规范要求闭围栏长度 >= 开围栏长度)。
  let openLen = 0;
  for (let i = 0; i < lines.length; i++) {
    const m = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[i]);
    if (!m) continue;
    if (openIdx === -1) {
      openIdx = i;
      openMark = m[1][0];
      openLen = m[1].length;
    } else if (
      m[1][0] === openMark &&
      m[1].length >= openLen &&
      m[2].trim() === ''
    ) {
      openIdx = -1;
    }
  }
  if (openIdx === -1) return { closedPart: text, openTail: '' };
  return {
    closedPart: lines.slice(0, openIdx).join('\n'),
    openTail: lines.slice(openIdx).join('\n'),
  };
};

interface MarkdownTextProps {
  text: string;
}

const MarkdownText: React.FC<MarkdownTextProps> = ({ text }) => {
  // §3.5 遗漏 5: 切分按 text 缓存, 长推理 × 高频 chunk 不再重复分段
  const { closedPart, openTail } = useMemo(
    () => findUnclosedFenceTail(text),
    [text]
  );

  const mdNode = useMemo(
    () =>
      closedPart ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}
          components={mdComponents}
        >
          {closedPart}
        </ReactMarkdown>
      ) : null,
    [closedPart]
  );

  // 无折叠分支: thought 长度不定, 阈值无意义(2026-10-05 北京老陈裁定, 详见文件头编辑历史)
  // 组件内无条件 return, 不存在"hook 数随内容变化"的风险
  return (
    <div style={{ whiteSpace: 'normal' }}>
      {mdNode}
      {/* 未闭合围栏尾段: 纯文本(pre-wrap 保留原换行), 不生成 <pre> 容器 → 页面零位移 */}
      {openTail && (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {openTail}
        </div>
      )}
    </div>
  );
};

export { MarkdownText };
export default MarkdownText;
