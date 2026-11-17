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
// 编辑历史: 2026-10-21 小杨 - 接入文件引用预处理（唯一预处理位，两个渲染分支共用）
//   ⚠ Hook 必须在早退之前（条件调用 Hook 会抛 "Rendered fewer hooks than expected"）— 小杨-2026-10-21
// 编辑历史: 2026-10-22 小欧 - 接入框线图(ASCII art)归一化(唯一位, 两个渲染分支共用):
//   渲染前把**围栏代码块内**的框线图按框局部对齐(显示列空间, 算法见 ./asciiArt.ts),
//   使 LLM 手画的框线在页面上不参差; 围栏外内容逐字不动, 普通代码块不受影响。
//   ⚠ 副作用: 复制按钮复制到的是"对齐版"文本(非原文)。 — 小欧-2026-10-22
// 2026-10-22 小欧 - **撤回上面的接入**: 框线图归一化暂不接入渲染层,
//   算法在 ./asciiArt.ts 内打磨, 接入点保留在本文件下方(artText 一行), 待验证通过后再接。 — 小欧-2026-10-22
// 2026-10-22 小欧 - **正式接入框线图(ASCII art)归一化**(北京老陈审核观感对照图后放行):
//   导入 normalizeMarkdownArt, 在 markdown=false 早退后算 artText, 两个渲染分支共用该入口;
//   接入前算法已完成: 边线行跟随内容行的规范几何 / 边界逐框认领 / 接头字符(┬┴┼)原位保留 /
//   误伤守卫(须含框角) / 宽度模型按 Sarasa Mono SC 实测口径。 — 小欧-2026-10-22
// 2026-11-02 小欧 - 取根触发判据改复用 projectPath.hasDriveAbsPath，删本文件内嵌盘符正则 — 小欧-2026-11-02
// 编辑历史: 2026-11-12 小欧 - **收口单渲染路径**(文档[30] §3 落地):
//   ①删 MD_IMPL 开关常量、MarkdownBody 的静态 import 与 MD_IMPL===1 分支 ——
//      MarkdownBody(手写正则仅 6 类子集: 无表格/引用/删除线/任务列表/图片)是**死分支**
//      (MD_IMPL 恒 0), 但被静态 import 白进主包, 且与 MarkdownText 各写一份标题/行内码/代码块
//      样式 → 排版双真源(违 DRY)。本次删 MarkdownBody.tsx, 只留 react-markdown 一条路径。
//   ②新增 scene / base / density 透传: 排版场景(文档[30] §4.3)与阅读区字号/界面密度设定项。
//   ③React.lazy 分块保留(纯文本用户不下载 react-markdown 三件套)。
import React from 'react';
import { useDeferredPreprocess } from './useDeferredPreprocess'; // 2026-10-21 小杨 - 文件引用预处理（流式期节流）
import { useProjectRoot } from '@/hooks/useProjectRoot';
import { hasDriveAbsPath } from '@/utils/projectPath';
import { normalizeMarkdownArt } from './asciiArt'; // 2026-10-22 小欧 - 框线图归一化(两渲染分支唯一入口)
import type { MdScene } from '@/utils/markdownStyles';
/** MD_IMPL=0 分支: lazy 分块, 避免纯文本用户下载 react-markdown 三件套 */
const MarkdownText = React.lazy(() => import('./MarkdownText'));

interface MarkdownSlotProps {
  text: string;
  /** 「思考排版」开关值(PipelineRenderer 顶层 hook 取一次后下传, 禁在 map 回调内调 hook) */
  markdown?: boolean;
  /**
   * 「表格按固定列宽排」开关: auto 布局下超长单元格会吃掉全部宽度、把窄列压成逐字竖排。
   * 仅安全Tab 分类表开, 聊天侧一律默认 auto, 零视觉变化。
   * — 小欧-2026-10-06
   */
  fixedTable?: boolean;
  /** 排版场景(取用区间, 文档[30] §4.3); 默认 chat = 流水线 */
  scene?: MdScene;
  /** 正文档位像素(仅 preview/doc 生效) */
  base?: number;
  /** 界面密度(仅阅读区间隔随其松紧; 流水线不消费) */
  density?: 'comfortable' | 'compact';
}

const MarkdownSlot: React.FC<MarkdownSlotProps> = ({
  text,
  markdown = false,
  fixedTable = false,
  scene = 'chat',
  base,
  density = 'comfortable',
}) => {
  // 2026-10-21 小杨 - 文件引用预处理**唯一位**（两分支共用，放这里两分支都吃到；
  //   放进 MarkdownText/MarkdownBody 内部会随 MD_IMPL 开关分叉）。
  //   ⚠ Hook 必须在所有早退之前 —— 条件调用 Hook 是 React 运行时错误。
  //   用 useDeferredPreprocess（流式期节流），不用裸 useMemo（每 chunk 全量跑正则）。
  // 2026-10-22 小欧 - 裸绝对路径按 projectRoot 归一（取不到时绝对路径保持原文，相对路径不受影响）
  //   只有出现盘符绝对路径才取根，纯文本/纯相对路径不打 /files/root
  // 2026-11-02 小欧 - 盘符判据改复用 utils/projectPath.hasDriveAbsPath（原内嵌一份正则，
  //   与正文识别的判据各写一遍）— 小欧-2026-11-02
  const projectRoot = useProjectRoot(hasDriveAbsPath(text));
  const safeText = useDeferredPreprocess(text, projectRoot);
  // 2026-10-22 小欧 - 框线图(ASCII art)归一化**唯一位**:
  //   归一化跑在 **deferred 文本**上: 急迫更新先出(原文), 归一化随后在稳定文本上补齐 ——
  //   与 useDeferredPreprocess 同款节流思路(DRY: 同一模式), 也顺带修掉下面的失实注释。
  //   ⚠ 原注释称"用 useMemo 记忆(依赖 safeText) → 免长消息 O(n²)"**不成立**:
  //     safeText 随流式每个 chunk 变 → memo 每次都重算, 流式期仍是 O(n²);
  //     且半截框线图(缺下边线)本就归一不了 → 纯白算。流式结束那一版 deferred 追平 → 最终对齐。
  //   ⚠ Hook 必须在所有早退之前(条件调用 Hook 是 React 运行时错误); 纯文本用户的代价仅为
  //   "无围栏即返回"的快速否决(一次字符串扫描)。
  //   两个渲染分支共用同一入口(放进分支内会随 MD_IMPL 开关分叉); 围栏外内容逐字不动, 普通代码块不受影响。
  //   ⚠ 副作用: 复制按钮复制到的是"对齐版"文本(非原文) —— 复制源 = PreBlock 的 children,
  //   而 children 来自 artText(MarkdownText.tsx:426 extractPlainText(props.children)) → 已核实。
  const deferredSafe = React.useDeferredValue(safeText);
  const artText = React.useMemo(
    () => normalizeMarkdownArt(deferredSafe),
    [deferredSafe]
  );
  if (!markdown) return <>{text}</>;
  return (
    <React.Suspense fallback={artText}>
      <MarkdownText
        text={artText}
        fixedTable={fixedTable}
        scene={scene}
        base={base}
        density={density}
      />
    </React.Suspense>
  );
};

export { MarkdownSlot };
export default MarkdownSlot;
