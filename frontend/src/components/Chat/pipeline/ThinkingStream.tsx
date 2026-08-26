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
        color: '#8c8c8c',
        fontStyle: 'italic',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: '4px 0',
      }}
    >
      {text}
      {cursor && <span className="thinking-cursor">▍</span>}
    </div>
  );
};

export { ThinkingStream };
