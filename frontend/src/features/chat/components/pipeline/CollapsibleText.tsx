// 编辑历史: 2026-08-26 小欧 - 8.11 实施: 长AI消息>30行/2000字折叠首2行+展开全文, 全局共用(4.4.3)
// 编辑历史: 2026-08-27 小欧 - 修复#7: 单行超长(无换行)文本按字符截断折叠, 不再整行展示(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 修复chat-G: 多行超长按首2行摘要, 不再按字符截断展现数十行(含第10行等)
// 编辑历史: 2026-08-28 小强 - 修复[19]: 多行折叠忽略maxChars, 首2行后按maxChars截断 - 小强-2026-08-28
// 编辑历史: 2026-08-28 小强 - 修复[20]: expanded状态不随text重置, 新消息默认折叠 - 小强-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 修复: 展开全文/收起链接onClick/onKeyDown加stopPropagation阻断冒泡(左列任务response折叠按钮误触外层onSelect→右栏自动展开, 北京老陈反馈) - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CT-01移除text变化强制setExpanded(false)防打断展开②CT-02 Typography.Link补onKeyDown Enter/Space键盘展开(无障碍) — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 BUG-16修复: text首100字符做key, 跨消息切换时重置expanded防状态残留
// 编辑历史: 2026-09-15 小欧 - 历史补记(工作区已落地改动核查补齐): 折叠切换由 Typography.Link 改 span role=button
//   (aria-expanded+Enter/Space 键盘), 支持展开/收起双向切换; 字号/间距令牌化(FontSize.SECONDARY/Spacing.SM/XS) — 小欧-2026-09-15
// 编辑历史: 2026-09-17 小沈 - 折叠按钮从左侧独占一行改为右侧对齐: 外层包 flex justifyContent:flex-end,
//   去掉 display:block/marginLeft, 按钮置于文本末行右侧, 视觉更协调 — 小沈-2026-09-17
// 编辑历史: 2026-09-17 小沈 - 折叠按钮改为内联跟在文本末尾不另起新行: 去掉外层 flex div,
//   span display:inline + whiteSpace:nowrap 直接跟在 shown 文本流末尾(最后一行右侧尾巴) — 小沈-2026-09-17
/**
 * CollapsibleText - 统一折叠组件（折叠非截断）
 *
 * 【小欧 2026-08-26 8.11】长 AI 消息 >5 行/200 字默认折叠为首2行摘要 +
 * "展开"；点击展开完整内容。ResponseStream 正文与 ToolCallLine 展开区长文本
 * 共用本组件（4.4.3 全局一份）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useMemo, useState } from 'react';
import { CircleArrow } from '@/components/CircleArrow';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

interface CollapsibleTextProps {
  text: string;
  maxLines?: number; // 默认 5 行阈值
  maxChars?: number; // 默认 200 字阈值
}

const CollapsibleText: React.FC<CollapsibleTextProps> = ({
  text,
  maxLines = 5,
  maxChars = 200,
}) => {
  const [expanded, setExpanded] = useState(false);
  // 2026-09-03 小欧 BUG-16修复: text变化(跨消息切换)时重置expanded, 用首100字符做key区分同消息内流式追加
  const _textKey = text.slice(0, 100);
  const _prevTextKeyRef = React.useRef(_textKey);
  React.useEffect(() => {
    if (_prevTextKeyRef.current !== _textKey) {
      setExpanded(false);
      _prevTextKeyRef.current = _textKey;
    }
  }, [_textKey]);
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

  const toggle = () => setExpanded((prev) => !prev);

  return (
    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {shown}
      {overflow && (
        <span
          role="button"
          tabIndex={0}
          aria-expanded={expanded}
          onClick={(e) => {
            e.stopPropagation();
            toggle();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              e.stopPropagation();
              toggle();
            } else {
              e.stopPropagation();
            }
          }}
          style={{
            fontSize: FontSize.SECONDARY,
            marginLeft: Spacing.XS,
            color: Colors.PRIMARY,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          <CircleArrow
            size={14}
            color={Colors.PRIMARY}
            expanded={expanded}
            animated={false}
          />
          {expanded ? ' 收起' : ' 展开'}
        </span>
      )}
    </div>
  );
};

export { CollapsibleText };
