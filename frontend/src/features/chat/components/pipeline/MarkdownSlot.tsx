// 编辑历史: 2026-10-05 小欧 - 新增: 「思考排版」开关下的**统一渲染入口**(北京老陈裁定:
//   思考内容段与最终答复段共用同一个开关, 不再按内容种类分开关)。
//   本组件集中三件事, TextStream / ResponseStream 两处消费端共用, 杜绝同一段逻辑写两遍:
//     ①markdown=false → 原样输出纯文本(两个调用方改动前的一字不改, 零退化);
//     ②markdown=true  → React.lazy 加载 MarkdownText(纯文本用户不下载三件套, 实测独立 chunk 163KB),
//                      加载期间用 Suspense fallback 显示**同一份纯文本**, 加载完自动切换为排版;
//     ③fallback 与关闭态共用同一份纯文本 → 加载完成前后内容一字不差, 只是排版有无, 无闪烁错位。
//   注: 两个调用方各自 React.lazy 同一模块时, 打包器按模块 id 去重 —— 网络上仍只请求一个 chunk,
//       故无需额外中转文件即可共享分块。 — 小欧-2026-10-05
import React from 'react';

// 2026-10-05 小欧: React.lazy 分块, 关闭开关的用户不下载 react-markdown 三件套(含 remark-gfm/
//   remark-breaks/rehype-sanitize)。与 TextStream 同一模块, 打包器去重后网络上只请求一次。
const MarkdownText = React.lazy(() => import('./MarkdownText'));

interface MarkdownSlotProps {
  text: string;
  /** 「思考排版」开关值(PipelineRenderer 顶层 hook 取一次后下传, 禁在 map 回调内调 hook) */
  markdown?: boolean;
}

const MarkdownSlot: React.FC<MarkdownSlotProps> = ({
  text,
  markdown = false,
}) => {
  if (!markdown) return <>{text}</>;
  return (
    <React.Suspense fallback={text}>
      <MarkdownText text={text} />
    </React.Suspense>
  );
};

export { MarkdownSlot };
export default MarkdownSlot;
