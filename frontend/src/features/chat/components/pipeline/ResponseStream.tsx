// 编辑历史: 2026-08-26 小欧 - 8.4.12 实施: 最终答复同列同等字号, cancelled弱化小字, 长文折叠(4.4.3/4.9.1④⑤/8.11)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P0-1: 段距margin6px0→8px0(正文/cancelled)统一流水线节奏
// 编辑历史: 2026-08-30 小欧 - 第十三章13.10.3.1+13.11(设计文档[2]13.12.5, 北京老陈 2026-08-30 批准): 段距落 Spacing.MD 常量(数值不变8px, 去魔法数字); 新增 normalizeBlankLines final 终态统一规约兜底(历史 answer 轮虽已压缩仍无条件兜底) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距改走 stepMargin(false)=(MD-2)=6, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(字体留白全0 + 行高=字号+4): 行高 `${FontSize.PRIMARY+Spacing.XS}px`(14+4=18), step 间 SM6 - 小欧-2026-08-30
// 编辑历史: 2026-09-11 小欧 - cancelled终止按成功/失败模式先状态后文字: 后端cancelled时response恒有值(cancel_terminal_text按来源出文案)
//   原写死"已取消"丢弃text(任务已被用户取消/连接中断多次重连失败等来源文案全丢); 改状态行"已取消"在前+正文渲染text(空则仅状态行) — 北京老陈-2026-09-11
// 编辑历史: 2026-09-11 小欧 - 北京老陈定案(最终): cancelled终态改由 PipelineRenderer 统一渲染(对齐failed模式):
//   首行response正常字号 + 第二行"✕ 取消来源: cancel_source"红字小字(符号换✕与取消相得益彰); 本组件回归纯正文,
//   删 cancelled prop 与弱化"已取消"分支(禁backward) — 北京老陈-2026-09-11
/**
 * ResponseStream - 最终答复流（纯正文）
 *
 * 【小欧 2026-08-26 8.4.12】4.4.3/4.9.1④ 最终答复不再"终态弱化收尾"——与思考流同列
 * 同等字号展示；长文包一层 CollapsibleText 折叠(8.11)。
 * 2026-09-11 北京老陈: cancelled 终态统一由 PipelineRenderer 渲染(首行response+第二行✕取消来源)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { CollapsibleText } from './CollapsibleText';
import { FontSize, Spacing, stepMargin } from '@/utils/stepStyles';
import { normalizeBlankLines } from '@/utils/textNormalize'; // 13.11 final 兜底 — 小欧 2026-08-30

interface ResponseStreamProps {
  text: string;
}

const ResponseStream: React.FC<ResponseStreamProps> = ({ text }) => {
  if (!text) return null;
  return (
    <div
      style={{
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: stepMargin(false),
        fontSize: FontSize.PRIMARY,
        lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
      }}
    >
      {/* 13.11 显示净: final 终态规约(历史 answer 轮虽已压缩, 仍无条件兜底) — 小欧 2026-08-30 */}
      <CollapsibleText text={normalizeBlankLines(text)} />
    </div>
  );
};

export { ResponseStream };