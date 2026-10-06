// 编辑历史: 2026-10-06 小欧 - MarkdownSlot 上移中立层后改指 @/components/markdown/MarkdownSlot(原 ./MarkdownSlot), 内容未改。 — 小欧-2026-10-06
// 编辑历史: 2026-08-26 小欧 - 8.4.12 实施: 最终答复同列同等字号, cancelled弱化小字, 长文折叠(4.4.3/4.9.1④⑤/8.11)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距修复: 段距margin6px0→8px0(正文/cancelled)统一流水线节奏
// 编辑历史: 2026-08-30 小欧 - 设计稿实施(北京老陈 2026-08-30 批准): 段距落 Spacing.MD 常量(数值不变8px, 去魔法数字); 新增 normalizeBlankLines final 终态统一规约兜底(历史 answer 轮虽已压缩仍无条件兜底) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距改走 stepMargin(false)=(MD-2)=6, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(字体留白全0 + 行高=字号+4): 行高 `${FontSize.PRIMARY+Spacing.XS}px`(14+4=18), step 间 SM6 - 小欧-2026-08-30
// 编辑历史: 2026-09-11 小欧 - cancelled终止按成功/失败模式先状态后文字: 后端cancelled时response恒有值(cancel_terminal_text按来源出文案)
//   原写死"已取消"丢弃text(任务已被用户取消/连接中断多次重连失败等来源文案全丢); 改状态行"已取消"在前+正文渲染text(空则仅状态行) — 北京老陈-2026-09-11
// 编辑历史: 2026-09-11 小欧 - 北京老陈定案(最终): cancelled终态改由 PipelineRenderer 统一渲染(对齐failed模式):
//   首行response正常字号 + 第二行"✕ 取消来源: cancel_source"红字小字(符号换✕与取消相得益彰); 本组件回归纯正文,
//   删 cancelled prop 与弱化"已取消"分支(禁backward) — 北京老陈-2026-09-11
// 编辑历史: 2026-09-13 小欧 - Prettier 格式统一(前端源码格式专项, 纯格式零逻辑): 对齐项目 prettier 排版规范 — 小欧-2026-09-13
// 编辑历史: 2026-10-05 小欧 v3.9 北京老陈裁定: ①最终答复段接入「思考排版」开关(与思考内容段共用,
//   不再按内容种类分开关—— 用户原话"答复段也是 thought text 的吧, 为什么要分开"); 实测证据: 改动前
//   答复里`**粗体**` 与 `- 列表` 一律原样纯文本(strong=0/ul=0), 而同屏思考段已渲染 Markdown,
//   表现为"开关开了却一点不起作用"; ②**删除 CollapsibleText 长文折叠** —— 原 >5行/>200字 折叠,
//   接入 Markdown 后折叠态与展开态都只能是纯文本(=把刚在 MarkdownText 删掉的同一坏行为搬回来),
//   故一并删除: 答复全文渲染, 不折叠(用户裁定"那就不折叠")。— 小欧-2026-10-05
/**
 * ResponseStream - 最终答复流（纯正文）
 *
 * 【小欧 2026-08-26 8.4.12】4.4.3/4.9.1④ 最终答复不再"终态弱化收尾"——与思考流同列
 * 同等字号展示。
 * 2026-09-11 北京老陈: cancelled 终态统一由 PipelineRenderer 渲染(首行response+第二行✕取消来源)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { CollapsibleText } from './CollapsibleText'; // 2026-10-05 小欧 v3.9.1: 仅 markdown=false 分支用(见文件头裁定) — 小欧-2026-10-05
import { FontSize, Spacing, stepMargin } from '@/utils/stepStyles';
import { normalizeBlankLines } from '@/utils/textNormalize'; // 13.11 final 兜底 — 小欧 2026-08-30
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot'; // 2026-10-05 小欧: 思考排版开关统一入口 — 小欧-2026-10-05

interface ResponseStreamProps {
  text: string;
  /**
   * 2026-10-05 小欧: 「思考排版」开关值, 由 PipelineRenderer 顶层 hook 取一次后下传。
   *   与思考内容段(TextStream)**共用同一个开关**; 关=原样纯文本(本次改动前行为, 零退化)。
   */
  markdown?: boolean;
}

const ResponseStream: React.FC<ResponseStreamProps> = ({
  text,
  markdown = false,
}) => {
  if (!text) return null;
  // 13.11 显示净: final 终态规约(历史 answer 轮虽已压缩, 仍无条件兜底) — 小欧 2026-08-30
  const clean = normalizeBlankLines(text);
  return (
    <div
      style={{
        // whiteSpace:pre-wrap 必须留: markdown=false 的纯文本折叠态靠它保留换行; wordBreak 服务超长串
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: stepMargin(false),
        fontSize: FontSize.PRIMARY,
        lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
      }}
    >
      {/* v3.9.1 北京老陈裁定(发现"删折叠会连关闭开关的老路径一起删掉"后修订):
          markdown=true  → 全量渲染不折叠(排版路径按裁定不设限; 且折叠态/展开态都只能是纯文本
                          = 把 MarkdownText 里刚删掉的同一坏行为搬回来, 故不折叠);
          markdown=false → **保留原 CollapsibleText 长文折叠**, 与本次改动前逐字一致, 零退化。 */}
      {markdown ? (
        <MarkdownSlot text={clean} markdown />
      ) : (
        <CollapsibleText text={clean} />
      )}
    </div>
  );
};

export { ResponseStream };
