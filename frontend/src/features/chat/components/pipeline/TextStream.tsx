// 编辑历史: 2026-08-30 小欧 - 13.8 实施: 正文 text 段真逐字打字机(打字机效果+末位光标), 回放/终态整段静态(13.8.5);
//   集成 13.10 step 间段距与 13.11 空行规约(normalizeBlankLines 尾随守卫);
//   2026-08-30 北京老陈定案纠正(step间8/内部6/折叠4): 主段12px(LG)废止 → margin 默认 MD(8)=step 间段距, compact=SM(6)=同 step 内部 - 小欧-2026-08-30
//   2026-08-30 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距走 stepMargin → 默认=(MD)-2=6, compact=(SM)-2=4, 数值不写死 - 小欧-2026-08-30
/**
 * TextStream - 正文打字机（真逐字 + 末位光标）
 *
 * 【小欧 2026-08-30 13.8】13.8.4 方案1 落地：streaming 实时按"已累积文本"逐字微延迟流出、
 * 末位闪烁光标（兑现文档1 §3.7.3.3"打字机效果"）；streaming 结束/历史回放整段静态呈现。
 * 内置 normalizeBlankLines（13.11）：流式走尾随守卫(防打字机回缩)、终态统一 trim。
 *
 * @author 小欧
 * @date 2026-08-30
 */
import React, { useEffect, useRef, useState } from 'react';
import { stepMargin } from '@/utils/stepStyles';
import { normalizeBlankLines } from '@/utils/textNormalize';

interface TextStreamProps {
  text: string;
  typing?: boolean; // 实时流且为本段累积中（打字机态）
  cursor?: boolean; // 末位闪烁光标
  compact?: boolean; // 同 step 内部(13.6 拆出的 reasoning→thought 相邻): 段距 SM(6)
}

const TextStream: React.FC<TextStreamProps> = ({
  text,
  typing = false,
  cursor = false,
  compact = false,
}) => {
  const clean = normalizeBlankLines(text, { streaming: typing });
  const [shown, setShown] = useState(0);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!typing) {
      setShown(clean.length); // 终态/回放: 整段静态
      return;
    }
    // 打字机: 已显示进度回续(单调递增不回缩), 步进按长度自适应(短文逐字、长文加速, ≤4s 打完)
    const step = Math.max(1, Math.ceil(clean.length / 240));
    timerRef.current = window.setInterval(() => {
      setShown((prev) => (prev >= clean.length ? prev : prev + step));
    }, 16);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [clean, typing]);

  return (
    <div
      style={{
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: stepMargin(compact), // 13.10.3 step 间段距 MD(8); 同 step 内部 compact→SM(6)
      }}
    >
      {clean.slice(0, typing ? shown : clean.length)}
      {cursor && typing && shown < clean.length && <span>▍</span>}
    </div>
  );
};

export { TextStream };
