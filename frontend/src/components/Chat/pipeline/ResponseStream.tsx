// 编辑历史: 2026-08-26 小欧 - 8.4.12 实施: 最终答复同列同等字号, cancelled弱化小字, 长文折叠(4.4.3/4.9.1④⑤/8.11)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P0-1: 段距margin6px0→8px0(正文/cancelled)统一流水线节奏
/**
 * ResponseStream - 最终答复流（取消弱化小字）
 *
 * 【小欧 2026-08-26 8.4.12】4.4.3/4.9.1④ 最终答复不再"终态弱化收尾"——与思考流同列
 * 同等字号展示；cancelled 仅弱化小字"已取消"（4.9.1⑤）；长文包一层 CollapsibleText
 * 折叠(8.11)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { CollapsibleText } from './CollapsibleText';

interface ResponseStreamProps {
  text: string;
  cancelled?: boolean;
}

const ResponseStream: React.FC<ResponseStreamProps> = ({
  text,
  cancelled = false,
}) => {
  if (!text && !cancelled) return null;
  if (cancelled) {
    return (
      <div
        style={{
          color: '#8c8c8c',
          fontSize: 13,
          fontStyle: 'italic',
          margin: '8px 0',
        }}
      >
        已取消
      </div>
    );
  }
  return (
    <div
      style={{
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: '8px 0',
        fontSize: 14,
        lineHeight: 1.8,
      }}
    >
      <CollapsibleText text={text} />
    </div>
  );
};

export { ResponseStream };
