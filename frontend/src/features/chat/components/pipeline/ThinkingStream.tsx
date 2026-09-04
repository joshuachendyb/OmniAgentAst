// 编辑历史: 2026-08-26 小欧 - 8.4.10 实施: 思考流灰斜体同列展开, 尾随呼吸光标(4.9.1②)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P0-1: 段距margin4px0→8px0统一流水线节奏(8点网格主节奏)
// 编辑历史: 2026-08-30 小欧 - 第十三章13.10.3.1+13.11(设计文档[2]13.12.4, 北京老陈 2026-08-30 批准): 段距落 Spacing.MD 常量(数值不变8px, 去魔法数字); 新增 normalizeBlankLines 显示入口(reasoning 段规约, 光标态即流式走尾随守卫防打字机回缩) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈定案纠正(step间8/内部6/折叠4): 加 compact prop, 同 step 内部(reasoning 与后置 thought 相邻)段距 SM(6), 默认仍是 MD(8)=step 间 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距走 stepMargin → 默认=(MD)-2=6, compact=(SM)-2=4, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(斜体视觉平衡): thought 斜体 14→12(secondary), 行高16(12+4), step间6/内4 层次不变 - 小欧-2026-08-30
/**
 * ThinkingStream - 思考流（灰斜体 + 尾随光标）
 *
 * 【小欧 2026-08-26 8.4.10】4.9.1② 思考块灰斜体且不再"单独折叠"——与正文同列
 * 顺序展开；实时思考末段尾随呼吸光标(.thinking-cursor)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Colors, FontSize, Spacing, stepMargin } from '@/utils/stepStyles';
import { normalizeBlankLines } from '@/utils/textNormalize'; // 13.11 显示兜底 — 小欧 2026-08-30

interface ThinkingStreamProps {
  text: string;
  cursor?: boolean; // 实时思考末段光标
  compact?: boolean; // 同 step 内部(13.6 拆出的 reasoning 与后置 thought 相邻): 段距 SM(6)
}

const ThinkingStream: React.FC<ThinkingStreamProps> = ({
  text,
  cursor = false,
  compact = false,
}) => {
  const clean = normalizeBlankLines(text, { streaming: cursor }); // 13.11: 思考段规约, 光标态(实时末段)走尾随守卫
  if (!text && !cursor) return null;
  return (
    <div
      className="thinking-stream"
      style={{
        color: Colors.TEXT.SECONDARY,
        fontSize: FontSize.SECONDARY,
        lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
        fontStyle: 'italic',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: stepMargin(compact),
      }}
    >
      {clean}
      {cursor && <span className="thinking-cursor">▍</span>}
    </div>
  );
};

export { ThinkingStream };
