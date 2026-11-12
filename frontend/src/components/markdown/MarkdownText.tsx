// 编辑历史: 2026-10-06 小欧 - 随 markdown 四件套从 features/chat/components/pipeline/ 整体上移到
//   components/markdown/ 中立层(解除 settings2 → chat 跨 feature 反向依赖)。本文件另加:
//   ①code 分支识别 language-mermaid 交 MermaidBlock 画流程图; ②pre 分支对 mermaid 围栏
//   不套代码块的边框/灰底/限高(靠 node 里的 hast className 判定); ③表格拆出 MdTable 支持
//   fixedTable(仅安全Tab 分类表用, 聊天侧默认 auto 观感不变); ④th/td 加 overflowWrap。
//   — 小欧-2026-10-06
// 编辑历史: 2026-10-05 小欧 - 新增: thought 思考段 Markdown 渲染器(参考代码落地, v3.7)
//   未闭合围栏尾段按纯文本渲染(避免空 <pre> 容器凭空出现致页面位移), 其余按 Markdown 渲染 — 小欧-2026-10-05
//   v2.1 自审整改(随参考代码一并落地): ①全部自定义组件显式剥 node 防泄漏到 DOM(react-markdown v9
//   必传 node, …rest 透传即非法属性, 禁止); ②remark-breaks 保留单换行(与 pre-wrap 现有效果一致);
//   ③schema 补 input 标签+属性(GFM 任务列表复选框否则被净化剥掉); ④标题保留语义标签只压样式;
//   ⑤切分与渲染按 text useMemo(防长推理×高频 chunk 重复全量解析) — 小欧-2026-10-05
//   v3.7 小欧 落地订正(与参考代码的两处偏差, 均因参考代码自身笔误/未跑过编译):
//     ①参考代码每个组件写成 ({ node, children }: any) 后又解构 `const { node, children } = p;`
//        —— `p` 未定义, 直接抄会 ReferenceError; 改为统一 (props: MdProps) + 解构 props。
//     ②参考代码 SANITIZE_SCHEMA 用 `...(defaultSchema.tagNames ?? [])` 兜空, 实测 defaultSchema.tagNames
//        恒为数组; 保留 ?? 兜底无副作用, 不改。
//     ③参考代码未用 FontFamily.MONO 令牌而是硬编码 'Consolas, Monaco, "Courier New", monospace',
//        与本仓 stepStyles 令牌化要求(复用优先)冲突 —— 改走 FontFamily.MONO 单一真相源。
//   v3.8 小欧 复核后修 4 项(有一项明确不修, 理由随附):
//     ①P1 真缺陷: pre 被覆盖成 <>{children}</> + code 靠 className 猜"是否围栏" —— 无语言围栏
//       (info string 为空时 hast 无 className)整段退化成行内 code, pre 数=0、块级样式全丢。
//       改法按语义归位: pre 管块级容器, code 管行内样式, 不加依赖不加插件不留分支。
//     ②P2 闭围栏长度未校验: 补 CommonMark 规则(闭围栏长度 >= 开围栏长度), 5 行内。
//     ③P3 wordBreak 与 overflow 语义抵消: 用户定案二选一, 选**横向滚动**(删折行)。
//     ④P4 `2*3*4` 渲染成 2<em>3</em>4: **不修**。这是 CommonMark 标准行为(单星号内不为空即成斜体),
//       旧自研版为防它写的正则属非标准 hack; 修它需再引 remark 插件自造偏离标准的行为, 违
//       "不自造轮子/KISS"且徒增维护面。如实回归标准并在此登记, 便于日后有人再问时有据可查。
//   v3.8.1 小欧 老陈指令: 围栏代码块右上角加"复制"按钮。pre 容器改为 PreBlock(position:relative + 绝对定位按钮,
//     复制源取原始children字符串不含按钮文字, copied后1.5s回退); code 组件不动(透传 className)。— 小欧-2026-10-05
//   申明订正: 上一条"已加复制按钮"为总结误报, 实际未落盘; 本次才真正落盘并入单测。— 小欧-2026-10-05
// 编辑历史: 2026-10-06 小欧 - MdTable 加 fontSize 参数(缺省 SECONDARY, 聊天侧零变化),
//   安全Tab 分类表传 PRIMARY: 该表是设置页正文(周围 14px), 用 12px 会小 2px 层级拉不开。 — 小欧-2026-10-06
// 编辑历史: 2026-10-21 小杨 - 接入文件引用 chip 与形态校验（与 FileRefChip 同源单一真源） — 小杨-2026-10-21
// 2026-10-22 小杨 - 文件引用链接的路径参数改走安全解码, 非法百分号编码不再抛 URIError — 小杨-2026-10-22
// 编辑历史: 2026-10-22 小欧 - 代码块显式行高 1.1: 原继承 1.5, │ 墨迹高 1.12–1.17em 行间留缝 →
//   框线竖线断成虚线; 行高 ≤1.14 时连成实线 — 小欧-2026-10-22
// 2026-10-22 小欧 - 文件引用分流放开外部路径：isValidRelPath 或 isExternalAbsPath（根外盘符绝对）
//   都渲染 FileRefChip（chip 内部分流外部预览）— 小欧-2026-10-22
// 2026-11-02 小欧 - a 组件按 `/file-ref?` 前缀分流到唯一链接组件 PathLink（原 FileRefChip）；
//   解析只调 parseFileRefLink（与 buildFileRefLink 同源），非法编码/形态非法退纯文本 — 小欧-2026-11-02
// 2026-11-02 小欧 - `/file-ref?` 前缀判据改调 projectPath.isFileRefLink，删本文件内联 startsWith — 小欧-2026-11-02
// 2026-11-02 小欧 - 正文 chip 传 pin：恢复旧 FileRefChip 的「别针」引用入口（合并时丢失）— 小欧-2026-11-02
// 编辑历史: 2026-11-12 小欧 - **排版全面改由 CSS 变量驱动**（文档[30] 落地）：
//   ①删全部内联字号/间距/颜色样式 —— 此前内联 style 与 index.css 的 .doc-body 类样式构成
//      双真源(类样式被内联压死, 连带 !important 补丁, 见文档[30] §2.4);
//      现由 utils/markdownStyles.ts 解算成 --md-* CSS 变量注入根节点, 样式规则统一在 index.css
//      的 .md-body 作用域 —— 单一真源, 零 !important。
//   ②新增 scene / base prop: 按文档[30] §4.3 的四场景取用区间 + §4.4 角色→档位映射排版。
//      默认 scene='chat' 保持流水线原有观感(h1/h2 16px / 正文 14px / 行高 1.35)。
//   ③补 img 组件(限宽+圆角+懒加载, 修复缺陷 #7)、补表格数字列右对齐 + 等宽数字、
//      补链接去 break-all(长 URL 不再拦腰截断)、补选中态/滚动条可见性。
//   ④行内代码改「浅灰底 + 深色字 + 品牌色左线」(对比度 11.7:1, 原蓝字蓝底仅 3.71:1 不达 AA)。
//   ⑤代码块行高双档: 普通代码取场景值(1.4/1.35), 含 ASCII 框线图的围栏仍取 1.1
//      (框线竖线墨迹高仅 1.12~1.17em, 行高大于此值竖线会断成虚线 —— 不可破)。
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { CopyButton } from './CopyButton';
// 2026-11-02 小欧 - 链接 UI 收敛到唯一组件 PathLink；形态门槛交由 resolvePathTarget — 小欧-2026-11-02
import { PathLink } from '@/components/PathLink';
import { MermaidBlock } from '@/components/mermaid/MermaidBlock';
import { isFileRefLink, parseFileRefLink } from '@/utils/projectPath';
import {
  codeBlockStyle,
  codeFenceLineHeight,
  isNumericCell,
  mdStyles,
  type MdScene,
} from '@/utils/markdownStyles';
// 密度词表唯一真源(2026-11-12 小欧 - 文档[32]): 组件 prop 不再自造字面量联合
import type { AppearanceDensity } from '@/constants/appearancePrefs';

/**
 * react-markdown v9 传给自定义组件的 props: 必含 node(hast 节点), 一律显式剥掉不得透传(缺陷 1)。
 */
interface MdProps {
  node?: unknown;
  children?: React.ReactNode;
  /** 围栏语言标记 language-js(渲染 code 块必需) */
  className?: string;
  href?: string;
  type?: string;
  checked?: boolean;
  alt?: string;
  src?: string;
}

// XSS 净化配置: 默认 schema(GitHub 风格, 天然覆盖 GFM 表格/删除线)之上只补两处缺口——
//   ① code[className]: 围栏语言标记(language-js)渲染所需, 默认被剥离(剥掉则无法区分围栏/行内代码)
//   ② input 标签 + type/checked/disabled: GFM 任务列表复选框所需, 默认整个标签被剥离
// 注意: 不补 a[target/rel]——外链属性由本文件 a 组件硬编码渲染(不从 hast 取), schema 无需放行
// 2026-11-12 小欧 - 补 img[src/alt/loading]: 图片规格(限宽/圆角/懒加载)需要这些属性,
//   默认 schema 放行 img 但剥 src/alt → 本文件 img 组件拿不到 src(缺陷 #7 无法修)
const SANITIZE_SCHEMA = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), 'input'],
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), 'className'],
    input: ['type', 'checked', 'disabled'],
    img: [...(defaultSchema.attributes?.img ?? []), 'src', 'alt'],
  },
};

// 2026-10-06 小欧 - 识别 pre 的内容是不是 mermaid 围栏(见下方 pre 组件的说明)
//   ⚠️ 不能靠 props.children 判: 实测 react-markdown v9 传给自定义组件的 children
//      是**普通对象**(constructor.name === 'Object'), React.isValidElement 恒 false。
//      改用 react-markdown 明确提供的 node(hast 元素): pre > code > properties.className。
//      node 只用于判断, 绝不透传到 DOM(禁透传)。
function isMermaidFence(node: unknown): boolean {
  const pre = node as
    | {
        children?: Array<{
          tagName?: string;
          properties?: { className?: string[] };
        }>;
      }
    | null
    | undefined;
  const code = pre?.children?.[0];
  return (
    code?.tagName === 'code' &&
    (code?.properties?.className ?? []).includes('language-mermaid')
  );
}

/** 取一段 React children 的纯文本(用于表格数字列判定 / 复制源) */
const extractPlainText = (node: React.ReactNode): string => {
  if (node == null || node === false) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractPlainText).join('');
  if (React.isValidElement(node)) {
    return extractPlainText(
      (node.props as { children?: React.ReactNode }).children
    );
  }
  return '';
};

/**
 * 切分未闭合围栏尾段: 打字机逐字喂入时 ``` 刚出头就成立, 直接渲染会凭空产一个空的 <pre>
 * 容器造成页面位移, 且尾段代码会被当成正文吞进 pre。返回 { closedPart: 可按 Markdown 渲染的前缀,
 * openTail: 未闭合尾段(按纯文本渲染) }。
 * 纯函数 15 行, 实时/历史同一规则通吃(已实测)。
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
  for (let i = 0; i < lines.length; i += 1) {
    const m = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[i] as string);
    if (!m) continue;
    if (openIdx === -1) {
      openIdx = i;
      // 2026-11-12 小欧 - 修回归: 原实现把 openMark 存成**整串**标记(如 '```'),
      //   闭合判定却拿闭围栏的**首字符**去比 → '`' === '```' 恒 false → 围栏永不闭合,
      //   于是已闭合代码块被误判成未闭合尾段(closedPart 被清空, pre 块不渲染)。
      //   判定只需知道标记**种类**(反引号 vs 波浪号), 长度另由 openLen 管 → 存首字符。
      openMark = (m[1] as string)[0] as string;
      openLen = (m[1] as string).length;
    } else if (
      (m[1] as string)[0] === openMark &&
      (m[1] as string).length >= openLen &&
      (m[2] as string).trim() === ''
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
  /** 表格按固定列宽排(见 MdTable); 默认 auto, 聊天侧表格观感不变 */
  fixedTable?: boolean;
  /** 排版场景(取用区间); 默认 chat = 流水线(观感与改动前一致) */
  scene?: MdScene;
  /** 正文档位像素(仅 preview/doc 场景生效; 缺省 14) */
  base?: number;
  /** 界面密度(仅阅读区间隔随其松紧; 流水线不消费) */
  density?: AppearanceDensity;
}

const MarkdownText: React.FC<MarkdownTextProps> = ({
  text,
  fixedTable = false,
  scene = 'chat',
  base,
  density = 'comfortable',
}) => {
  // 遗漏 5: 切分按 text 缓存, 长推理 × 高频 chunk 不再重复分段
  const { closedPart, openTail } = useMemo(
    () => findUnclosedFenceTail(text),
    [text]
  );

  // 2026-11-12 小欧 - 排版变量解算(唯一真源 utils/markdownStyles.ts)
  const styles = useMemo(
    () => mdStyles(scene, base, density),
    [scene, base, density]
  );

  const mdNode = useMemo(
    () =>
      closedPart ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}
          components={buildComponents(styles, fixedTable)}
        >
          {closedPart}
        </ReactMarkdown>
      ) : null,
    [closedPart, fixedTable, styles]
  );

  // 无折叠分支: thought 长度不定, 阈值无意义(2026-10-05 用户定案, 详见文件头编辑历史)
  // 组件内无条件 return, 不存在"hook 数随内容变化"的风险
  return (
    <div className={styles.rootClass} style={styles.vars}>
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

/**
 * 生成 react-markdown 组件映射。
 *   样式一律走 .md-body 作用域(CSS 变量注入根节点), 此处**零内联字号/间距/颜色**。
 *   仅三处必须内联:
 *     ①复制按钮的绝对定位(pre 需 position:relative, 按钮贴右上角);
 *     ②框线图围栏的 1.1 行高(依围栏内容判定, CSS 无法表达);
 *     ③表格 fixed 布局的 tableLayout(设置页分类表专用)。
 */
const buildComponents = (
  styles: ReturnType<typeof mdStyles>,
  fixedTable: boolean
) => {
  const codeLineHeight = styles.codeLineHeight;
  // 2026-10-06 小欧 - md 表格容器。fixed 模式用于安全Tab 分类表(auto 下超长单元格会独占宽度)。
  //   2026-11-12 小欧 - 表格字号改由 .md-body 作用域的 --md-fs-table 决定, 不再由组件传字号。
  const MdTable: React.FC<MdProps> = ({ children }) => (
    <div className="md-table-scroll">
      <table style={fixedTable ? { tableLayout: 'fixed' } : undefined}>
        {children}
      </table>
    </div>
  );

  // Markdown 元素样式映射: 全部走 index.css 的 .md-body 作用域, 零硬编码颜色
  // 规则: 所有组件必须显式丢弃 node(缺陷 1), 禁止 ...rest 透传到 DOM
  // 标题保留语义标签 h1..h6(a11y 大纲不断), 只统一样式压小(遗漏 4)
  return {
    h1: (props: MdProps) => <h1>{props.children}</h1>,
    h2: (props: MdProps) => <h2>{props.children}</h2>,
    h3: (props: MdProps) => <h3>{props.children}</h3>,
    h4: (props: MdProps) => <h4>{props.children}</h4>,
    h5: (props: MdProps) => <h5>{props.children}</h5>,
    h6: (props: MdProps) => <h6>{props.children}</h6>,
    p: (props: MdProps) => <p>{props.children}</p>,
    ul: (props: MdProps) => <ul>{props.children}</ul>,
    ol: (props: MdProps) => <ol>{props.children}</ol>,
    li: (props: MdProps) => <li>{props.children}</li>,
    blockquote: (props: MdProps) => <blockquote>{props.children}</blockquote>,
    hr: () => <hr />,
    // className 原样透传: 围栏语言标记(language-js)是 react-markdown 挂在 code 节点上的唯一可观测
    //   信息(设计要求保留, SANITIZE_SCHEMA 亦为它放行 className), 丢了就只剩肉眼看不出区别的
    //   两种代码块; 行内代码 hast 上无此属性, React 自动省略该属性, 无需条件分支。
    // 2026-10-06 小欧: ```mermaid 围栏交给 MermaidBlock 画流程图, 其余照旧走代码块样式。
    //   className 是 react-markdown 挂在 code 节点上的唯一可观测信息(见上方注释), 故据此分流。
    code: (props: MdProps) => {
      if (props.className === 'language-mermaid') {
        const raw = Array.isArray(props.children)
          ? props.children.join('')
          : String(props.children ?? '');
        return <MermaidBlock chart={raw.trim()} />;
      }
      return <code className={props.className}>{props.children}</code>;
    },
    // pre 块级容器: 直接渲染, 由本组件负责块级样式。
    // 2026-10-05 小欧 P1 修复(原实现把 pre 覆盖成 <>{children}</> 让 code 组件自行产 pre, 靠 className
    //   判断"是否围栏"): react-markdown v9 中 **info string 为空时 hast 的 code 节点没有 className**,
    //   故 ```\nplain\n``` 这类无语言围栏被误判为行内代码, 且 pre 覆盖又把块级容器一并抹掉 →
    //   实测 pre 数=0, 多行代码挤成一行内联、换行压平、左线/限高/等宽块样式全丢(thought 贴代码极常见)。
    // 现按语义归位: pre = 块级容器(本组件), code = 行内样式(不论在不在 pre 内, 前者字体/换行由 pre 管) — 小欧-2026-10-05
    // 2026-10-06 小欧(复核 #1): mermaid 围栏不走 PreBlock —— 代码块的边框/灰底/400px 限高
    //   会把流程图压成一个带滚动条的代码框, 图还被截断。识别靠 code 组件打的 data-md-fence 标记。
    //   连带修掉 #18: 不再需要 CSS `pre:has(.mermaid-block)` 隐藏复制按钮(老浏览器 :has() 不生效)。
    pre: (props: MdProps) =>
      isMermaidFence(props.node) ? (
        <div>{props.children}</div>
      ) : (
        <PreBlock {...props} lineHeightFallback={codeLineHeight} />
      ),
    // 2026-10-21 小杨 - 文件引用链接分流 —— /file-ref?path=… 渲染成 PathLink（App 内跳转）
    //   ⚠ 绝不能直接复用下面的 <a>：它硬编码 target="_blank" → 文件引用会**新开浏览器标签页**（桌面端灾难）。
    //   故在 a 组件内提前 return，按 href 前缀分流。
    a: (props: MdProps) => {
      const href = props.href ?? '';
      // 2026-11-02 小欧 - 只有 /file-ref? 前缀才进路径分支；href 解析交唯一解析点
      // parseFileRefLink（与 buildFileRefLink 同源）— 小欧-2026-11-02
      if (isFileRefLink(href)) {
        const parts = parseFileRefLink(href);
        // 非法百分号编码 / 形态非法 → 退化纯文本，不造假链接
        if (!parts) return <>{props.children}</>;
        return (
          <PathLink rawPath={parts.rawPath} lineRange={parts.lineRange} pin />
        );
      }
      return (
        <a href={props.href} target="_blank" rel="noopener noreferrer">
          {props.children}
        </a>
      );
    },
    // 2026-11-12 小欧 - 补 img 组件(缺陷 #7: 图片无任何样式, 大图溢出容器):
    //   限宽 + 圆角 + 懒加载(长文档多图不阻塞首屏); alt 由净化 schema 放行, 缺 alt 时保留原值。
    img: (props: MdProps) => (
      <img src={props.src} alt={props.alt ?? ''} loading="lazy" />
    ),
    table: (props: MdProps) => <MdTable {...props} />,
    thead: (props: MdProps) => <thead>{props.children}</thead>,
    // 2026-10-06 小欧: 长 token 可断行。分类表的「目录列表」列有超长路径
    //   (如 \Windows\System32\config\SECURITY), 不断行会把该列撑到极宽、其余列被挤成逐字竖排。
    //   ⚠️ 本项目未装 rehype-raw, md 里的 <br/> 会被 rehype-sanitize 整段丢弃, 故 md 单元格
    //   一律用「、」分隔 + 靠本行折行, 不要写 <br/>。
    th: (props: MdProps) => <th>{props.children}</th>,
    // 2026-11-12 小欧 - 数字列右对齐 + 等宽数字(列内小数点对齐): 由单元格文本判定,
    //   判定规则在 utils/markdownStyles 的 isNumericCell(唯一真源)。
    td: (props: MdProps) => {
      const numeric = isNumericCell(extractPlainText(props.children));
      return <td className={numeric ? 'md-num' : undefined}>{props.children}</td>;
    },
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
      />
    ),
  };
};

// 2026-10-05 小欧 - 围栏代码块右上角"复制"按钮(老陈指令):
//   取原始 children 字符串做复制源(不含按钮文字, 保证复制=代码原文), 复制后 1.5s 变"已复制"回退。
const PreBlock: React.FC<MdProps & { lineHeightFallback: number }> = (
  props
) => {
  // 2026-10-05 小欧: 按钮交互抽到共用 CopyButton(消除本文件与 MarkdownBody 重复实现, DRY)。
  //   复制源=extractPlainText(props.children) 取原始字符串(不含按钮文字); 详见 CopyButton.tsx。
  // 2026-11-12 小欧 - 框线图围栏行高兜底: 含框线字符的行高须为 1.1(竖线墨迹高仅 1.12~1.17em,
  //   行高大于此值竖线断成虚线 —— 既有结论, 不可破)。判定规则在 utils/markdownStyles(唯一真源)。
  //   普通代码不写内联行高(走 CSS 变量 --md-lh-code-block), 只有框线图才覆盖。
  const content = extractPlainText(props.children);
  const lineHeight = codeFenceLineHeight(content, props.lineHeightFallback);
  return (
    <pre
      style={{
        // 2026-11-12 小欧 - 代码块行为属性(P3 横向滚动)归 TS 单一真源:
        //   原写在 index.css 的 .md-body pre 里, 但 max-height 400px 是**数字**写在 CSS,
        //   违[30]「数字与颜色只在 TS 一处, CSS 只消费变量」; 且 CSS 侧那四条与本文件
        //   内联行为样式各写一份 → 双源。现统一由 utils/markdownStyles 的 codeBlockStyle 给出,
        //   CSS 侧已删除对应声明(数值完全一致 → 视觉零变化)。
        ...codeBlockStyle,
        ...(lineHeight === props.lineHeightFallback
          ? {}
          : { lineHeight }),
      }}
    >
      <CopyButton text={content} />
      {props.children}
    </pre>
  );
};

export { MarkdownText };
export default MarkdownText;
