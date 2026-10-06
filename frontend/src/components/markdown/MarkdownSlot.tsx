// 编辑历史: 2026-10-06 小欧 - 随 markdown 四件套从 features/chat/components/pipeline/ 整体上移到
//   components/markdown/ 中立层: 安全Tab 块2 要用 MarkdownSlot, 留在 chat 下就成了
//   settings2 → chat 的跨 feature 反向依赖。本文件另加 fixedTable 开关(仅安全Tab 分类表用)。
//   — 小欧-2026-10-06
// 编辑历史: 2026-10-05 小欧 - 新增: 「思考排版」开关下的**统一渲染入口**(北京老陈裁定:
//   思考内容段与最终答复段共用同一个开关, 不再按内容种类分开关)。
//   集中三件事, TextStream / ResponseStream 两处消费端共用, 杜绝同一段逻辑写两遍:
//     ①markdown=false → 原样输出纯文本(两个调用方改动前的一字不改, 零退化);
//     ②markdown=true  → 按 MD_IMPL 走对应渲染器;
//     ③MD_IMPL=0 分支用 React.lazy 分块(react-markdown 三件套 163KB, 纯文本用户不下载),
//       MD_IMPL=1 分支零依赖手写正则, 无需分块。 — 小欧-2026-10-05
// 编辑历史: 2026-10-05 小欧 北京老陈裁定: 加**代码内切换变量 MD_IMPL**, 0/1 两版并存可比:
//     0 = MarkdownText.tsx(react-markdown, 34 类格式, XSS 净化)
//     1 = MarkdownBody.tsx(零依赖手写正则, 6 类子集: 围栏码块/行内码/粗体/斜体/1~3级标题/无序列表)
//   两文件同在 components/markdown/ 目录, 改这一个数字即切换, 无需改任何调用方。 — 小欧-2026-10-05
import React from 'react';
import { MarkdownBody } from './MarkdownBody'; // MD_IMPL=1 分支(零依赖, 静态引入)
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
   * 2026-10-06 小欧: 表格按固定列宽排(auto 布局下超长单元格会吃掉全部宽度、把窄列压成逐字竖排)。
   *   仅安全Tab 分类表开 —— 聊天侧一律保持默认 auto, 零视觉变化。
   *   ⚠️ 仅 MD_IMPL=0(react-markdown) 分支支持; MD_IMPL=1 的 MarkdownBody 不解析表格, 该参数无效。
   */
  fixedTable?: boolean;
}

const MarkdownSlot: React.FC<MarkdownSlotProps> = ({
  text,
  markdown = false,
  fixedTable = false,
}) => {
  if (!markdown) return <>{text}</>;
  // 2026-10-06 小欧(三堂会审 #5): MD_IMPL=1 的 MarkdownBody 根本不解析表格(无表格支持),
  //   fixedTable 在该分支无处可施。此前无任何说明, 切 MD_IMPL 会让调用方以为生效了。
  //   显式在此标注该分支的局限, 避免"静默失效"。
  if (MD_IMPL === 1) return <MarkdownBody text={text} />;
  return (
    <React.Suspense fallback={text}>
      <MarkdownText text={text} fixedTable={fixedTable} />
    </React.Suspense>
  );
};

export { MarkdownSlot };
export default MarkdownSlot;
