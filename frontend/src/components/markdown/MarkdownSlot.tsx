// 编辑历史: 2026-10-06 小欧 - 随 markdown 四件套从 features/chat/components/pipeline/ 整体上移到
//   components/markdown/ 中立层: 安全Tab 块2 要用 MarkdownSlot, 留在 chat 下就成了
//   settings2 → chat 的跨 feature 反向依赖。本文件另加 fixedTable 开关(仅安全Tab 分类表用)。
//   — 小欧-2026-10-06
// 编辑历史: 2026-10-05 小欧 - 新增: 「思考排版」开关下的**统一渲染入口**(
//   思考内容段与最终答复段共用同一个开关, 不再按内容种类分开关)。
//   集中三件事, TextStream / ResponseStream 两处消费端共用, 杜绝同一段逻辑写两遍:
//     ①markdown=false → 原样输出纯文本(两个调用方改动前的一字不改, 零退化);
//     ②markdown=true  → 按 MD_IMPL 走对应渲染器;
//     ③MD_IMPL=0 分支用 React.lazy 分块(react-markdown 三件套 163KB, 纯文本用户不下载),
//       MD_IMPL=1 分支零依赖手写正则, 无需分块。 — 小欧-2026-10-05
// 编辑历史: 2026-10-05 小欧 - 加**代码内切换变量 MD_IMPL**, 0/1 两版并存可比:
//     0 = MarkdownText.tsx(react-markdown, 34 类格式, XSS 净化)
//     1 = MarkdownBody.tsx(零依赖手写正则, 6 类子集: 围栏码块/行内码/粗体/斜体/1~3级标题/无序列表)
//   两文件同在 components/markdown/ 目录, 改这一个数字即切换, 无需改任何调用方。 — 小欧-2026-10-05
// 编辑历史: 2026-10-06 小欧 - 新增 fixedTable: 表格按固定列宽排(仅安全Tab 分类表用) — 小欧-2026-10-06
// 编辑历史: 2026-10-21 小杨 - 接入文件引用预处理（唯一预处理位，两分支共用）
//   ⚠ Hook 必须在早退之前（条件调用 Hook 会抛 "Rendered fewer hooks than expected"）— 小杨-2026-10-21
// 编辑历史: 2026-10-22 小欧 - 接入框线图(ASCII art)归一化(唯一位, 两个渲染分支共用):
//   渲染前把**围栏代码块内**的框线图按框局部对齐(显示列空间, 算法见 ./asciiArt.ts),
//   使 LLM 手画的框线在页面上不参差; 围栏外内容逐字不动, 普通代码块不受影响。
//   ⚠ 副作用: 复制按钮复制到的是"对齐版"文本(非原文)。 — 小欧-2026-10-22
// 编辑历史: 2026-10-22 小欧 - **撤回上面的接入**: 框线图归一化暂不接入渲染层,
//   算法在 ./asciiArt.ts 内打磨, 接入点保留在本文件下方(artText 一行), 待验证通过后再接。 — 小欧-2026-10-22
// 编辑历史: 2026-10-22 小欧 - 裸绝对路径需项目根归一: 取 useProjectRoot 下传预处理 — 小欧-2026-10-22
// 编辑历史: 2026-10-22 小欧 - **正式接入框线图(ASCII art)归一化**(北京老陈审核观感对照图后放行):
//   导入 normalizeMarkdownArt, 在 markdown=false 早退后算 artText, 两个渲染分支共用该入口;
//   接入前算法已完成: 边线行跟随内容行的规范几何 / 边界逐框认领 / 接头字符(┬┴┼)原位保留 /
//   误伤守卫(须含框角) / 宽度模型按 Sarasa Mono SC 实测口径。 — 小欧-2026-10-22
import React from 'react';
import { MarkdownBody } from './MarkdownBody'; // MD_IMPL=1 分支(零依赖, 静态引入)
import { useDeferredPreprocess } from './useDeferredPreprocess'; // 2026-10-21 小杨 - 文件引用预处理（流式期节流）
import { useProjectRoot } from '@/hooks/useProjectRoot';
import { normalizeMarkdownArt } from './asciiArt'; // 2026-10-22 小欧 - 框线图归一化(两渲染分支唯一入口)
/** MD_IMPL=0 分支: lazy 分块, 避免纯文本用户下载 react-markdown 三件套 */
const MarkdownText = React.lazy(() => import('./MarkdownText'));

/**
 * 思考排版渲染实现切换变量(0/1) —— 唯一改动点。
 * 0 = MarkdownText.tsx: react-markdown 真 CommonMark 解析, 34 类格式(表格/删除线/任务列表/图片/
 *     引用/嵌套列表…), rehype-sanitize 净化, 缺点=5 个依赖 + 163KB。
 * 1 = MarkdownBody.tsx: 零依赖手写正则逐行解析, 6 类子集, 优点=轻量/行级 pre-wrap 原样保留缩进,
 *     缺点=不认有序列表/表格/删除线等(其余按纯文本原样显示)。
 */
//   注意: 用 `0 as 0 | 1` 断言而非 `const x: 0|1 = 0` —— 后者会被 TS 按初始化值窄化成字面量 0,
//   另一分支 `MD_IMPL === 1` 直接报 TS2367(无交集), 改一个数字就得动类型。断言保住联合类型, 两分支恒合法。
const MD_IMPL = 0 as 0 | 1;

interface MarkdownSlotProps {
  text: string;
  /** 「思考排版」开关值(PipelineRenderer 顶层 hook 取一次后下传, 禁在 map 回调内调 hook) */
  markdown?: boolean;
  /**
   * 「表格按固定列宽排」开关: auto 布局下超长单元格会吃掉全部宽度、把窄列压成逐字竖排。
   * 仅安全Tab 分类表开, 聊天侧一律默认 auto, 零视觉变化。
   * ⚠️ 仅 MD_IMPL=0(react-markdown) 分支支持; MD_IMPL=1 的 MarkdownBody 不解析表格, 该参数无效。
   * — 小欧-2026-10-06
   */
  fixedTable?: boolean;
}

const MarkdownSlot: React.FC<MarkdownSlotProps> = ({
  text,
  markdown = false,
  fixedTable = false,
}) => {
  // 2026-10-21 小杨 - 文件引用预处理**唯一位**（两分支共用，放这里两分支都吃到；
  //   放进 MarkdownText/MarkdownBody 内部会随 MD_IMPL 开关分叉）。
  //   ⚠ Hook 必须在所有早退之前 —— 条件调用 Hook 是 React 运行时错误。
  //   用 useDeferredPreprocess（流式期节流），不用裸 useMemo（每 chunk 全量跑正则）。
  //   2026-10-22 小欧 - 裸绝对路径按 projectRoot 归一（取不到时绝对路径保持原文，相对路径不受影响）
  //   只有出现盘符绝对路径才取根，纯文本/纯相对路径不打 /files/root
  const projectRoot = useProjectRoot(
    /(?:^|[^A-Za-z0-9+.-])[A-Za-z]:[\\/]/.test(text)
  );
  const safeText = useDeferredPreprocess(text, projectRoot);
  // 2026-10-22 小欧 - 框线图(ASCII art)归一化**唯一位**(北京老陈 2026-10-22 审核观感截图后放行):
  //   用 useMemo 记忆(依赖 safeText) —— 否则父组件每重渲染一次就全量重扫+重排整篇
  //   (流式期每 chunk 一次) → 长消息 O(n²)。
  //   ⚠ Hook 必须在所有早退之前(条件调用 Hook 是 React 运行时错误); 纯文本用户的代价仅为
  //   "无围栏即返回"的快速否决(一次字符串扫描)。
  //   两个渲染分支共用同一入口(放进分支内会随 MD_IMPL 开关分叉); 围栏外内容逐字不动, 普通代码块不受影响。
  //   ⚠ 副作用: 复制按钮复制到的是"对齐版"文本(非原文) —— 复制源 = PreBlock 的 children,
  //   而 children 来自 artText(MarkdownText.tsx:426 extractPlainText(props.children)) → 已核实。
  const artText = React.useMemo(
    () => normalizeMarkdownArt(safeText),
    [safeText]
  );
  if (!markdown) return <>{text}</>;
  // 2026-10-06 小欧(三堂会审 #5): MD_IMPL=1 的 MarkdownBody 根本不解析表格(无表格支持),
  //   fixedTable 在该分支无处可施。此前无任何说明, 切 MD_IMPL 会让调用方以为生效了。
  //   现于此处标注该分支的局限, 避免"静默失效"。
  if (MD_IMPL === 1) return <MarkdownBody text={artText} />;
  return (
    <React.Suspense fallback={artText}>
      <MarkdownText text={artText} fixedTable={fixedTable} />
    </React.Suspense>
  );
};

export { MarkdownSlot };
export default MarkdownSlot;
