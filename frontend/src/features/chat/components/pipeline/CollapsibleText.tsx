// 编辑历史: 2026-08-26 小欧 - 8.11 实施: 长AI消息>30行/2000字折叠首2行+展开全文, 全局共用(4.4.3)
// 编辑历史: 2026-08-27 小欧 - 修复#7: 单行超长(无换行)文本按字符截断折叠, 不再整行展示(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 修复chat-G: 多行超长按首2行摘要, 不再按字符截断展现数十行(含第10行等)
// 编辑历史: 2026-08-28 小强 - 修复[19]: 多行折叠忽略maxChars, 首2行后按maxChars截断 - 小强-2026-08-28
// 编辑历史: 2026-08-28 小强 - 修复[20]: expanded状态不随text重置, 新消息默认折叠 - 小强-2026-08-28
/**
 * CollapsibleText - 统一折叠组件（折叠非截断）
 *
 * 【小欧 2026-08-26 8.11】长 AI 消息 >30 行/2000 字默认折叠为首2行摘要 +
 * "展开全文"；点击展开完整内容。ResponseStream 正文与 ToolCallLine 展开区长文本
 * 共用本组件（4.4.3 全局一份）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Typography } from 'antd';

interface CollapsibleTextProps {
  text: string;
  maxLines?: number; // 默认 30 行阈值
  maxChars?: number; // 默认 2000 字阈值
}

const CollapsibleText: React.FC<CollapsibleTextProps> = ({
  text,
  maxLines = 30,
  maxChars = 2000,
}) => {
  const [expanded, setExpanded] = useState(false);
  useEffect(() => setExpanded(false), [text]);
  const overflow = useMemo(() => {
    const lineCount = text.split('\n').length;
    return lineCount > maxLines || text.length > maxChars;
  }, [text, maxLines, maxChars]);

  const shown = useMemo(() => {
    if (!overflow || expanded) return text;
    const lines = text.split('\n');
    // 2026-08-27 小欧 修复: 多行内容优先取首2行摘要(BUG-G), 单行超长无换行才按字符截断(修复#7)
    if (lines.length > 1) {
      const preview = lines.slice(0, 2).join('\n');
      if (preview.length > maxChars) return preview.slice(0, maxChars) + '…';
      return preview;
    }
    if (text.length > maxChars) return text.slice(0, maxChars) + '…';
    return text;
  }, [text, overflow, expanded, maxChars]);

  return (
    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {shown}
      {overflow && !expanded && (
        <Typography.Link
          onClick={() => setExpanded(true)}
          style={{ fontSize: 12, marginLeft: 8 }}
        >
          展开全文
        </Typography.Link>
      )}
      {overflow && expanded && (
        <Typography.Link
          onClick={() => setExpanded(false)}
          style={{ fontSize: 12, marginLeft: 8 }}
        >
          收起
        </Typography.Link>
      )}
    </div>
  );
};

export { CollapsibleText };
