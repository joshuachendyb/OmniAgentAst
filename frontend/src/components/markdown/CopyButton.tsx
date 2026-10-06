// 编辑历史: 2026-10-06 小欧 - 随 markdown 四件套从 features/chat/components/pipeline/ 整体上移到
//   components/markdown/ 中立层(解除 settings2 → chat 跨 feature 反向依赖)。
//   本文件内容逐字未改, 仅换目录。 — 小欧-2026-10-06
// 编辑历史: 2026-10-05 小欧 - 新增: 代码块右上角"复制"小按钮共用组件(老陈指令)。
//   原MarkdownText的PreBlock与MarkdownBody各写了一份同款逻辑(violation: DRY重复), 抽为单一来源 — 小欧-2026-10-05
import React, { useState } from 'react';
import { BorderWidth, Colors, Radius, Spacing } from '@/utils/stepStyles';

interface CopyButtonProps {
  /** 点击复制的原文(必须由调用方保证不含按钮自身的文本) */
  text: string;
}

/** 代码块右上角"复制"按钮: 点击写剪贴板, 1.5s 后回退为"已复制" — 2026-10-05 小欧 */
const CopyButton: React.FC<CopyButtonProps> = ({ text }) => {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 剪贴板不可用时静默 */
    }
  };
  return (
    <button
      type="button"
      onClick={onCopy}
      aria-label={copied ? '已复制' : '复制代码'}
      style={{
        position: 'absolute',
        top: Spacing.XS - 2,
        right: Spacing.XS,
        fontSize: 11,
        lineHeight: '14px',
        padding: '2px 6px',
        border: `${BorderWidth.THIN}px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: Radius.SM,
        background: Colors.BG.PRIMARY,
        color: Colors.TEXT.SECONDARY,
        cursor: 'pointer',
      }}
    >
      {copied ? '已复制' : '复制'}
    </button>
  );
};

export { CopyButton };
export default CopyButton;
