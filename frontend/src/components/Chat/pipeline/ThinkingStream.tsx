// 编辑历史: 2026-08-26 小欧 - 8.4.10 实施: 思考流灰斜体同列展开, 尾随呼吸光标(4.9.1②)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P0-1: 段距margin4px0→8px0统一流水线节奏(8点网格主节奏)
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
import { Colors } from '@/utils/stepStyles';

interface ThinkingStreamProps {
  text: string;
  cursor?: boolean; // 实时思考末段光标
}

const ThinkingStream: React.FC<ThinkingStreamProps> = ({
  text,
  cursor = false,
}) => {
  if (!text && !cursor) return null;
  return (
    <div
      className="thinking-stream"
      style={{
        color: Colors.TEXT.SECONDARY,
        fontStyle: 'italic',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: '8px 0',
      }}
    >
      {text}
      {cursor && <span className="thinking-cursor">▍</span>}
    </div>
  );
};

export { ThinkingStream };
