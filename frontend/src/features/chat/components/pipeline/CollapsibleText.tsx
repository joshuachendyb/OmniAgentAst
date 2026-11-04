// 编辑历史: 2026-08-26 小欧 - 8.11 实施: 长AI消息>30行/2000字折叠首2行+展开全文, 全局共用(4.4.3)
// 编辑历史: 2026-08-27 小欧 - 修复#7: 单行超长(无换行)文本按字符截断折叠, 不再整行展示(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 修复chat-G: 多行超长按首2行摘要, 不再按字符截断展现数十行(含第10行等)
// 编辑历史: 2026-08-28 小强 - 修复: 多行折叠忽略maxChars, 首2行后按maxChars截断 - 小强-2026-08-28
// 编辑历史: 2026-08-28 小强 - 修复: expanded状态不随text重置, 新消息默认折叠 - 小强-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 修复: 展开全文/收起链接onClick/onKeyDown加stopPropagation阻断冒泡(左列任务response折叠按钮误触外层onSelect→右栏自动展开, 北京老陈反馈) - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CT-01移除text变化强制setExpanded(false)防打断展开②CT-02 Typography.Link补onKeyDown Enter/Space键盘展开(无障碍) — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 修复: text首100字符做key, 跨消息切换时重置expanded防状态残留
// 编辑历史: 2026-09-15 小欧 - 历史补记(工作区已落地改动核查补齐): 折叠切换由 Typography.Link 改 span role=button
//   (aria-expanded+Enter/Space 键盘), 支持展开/收起双向切换; 字号/间距令牌化(FontSize.SECONDARY/Spacing.SM/XS) — 小欧-2026-09-15
// 编辑历史: 2026-09-17 小沈 - 折叠按钮从左侧独占一行改为右侧对齐: 外层包 flex justifyContent:flex-end,
//   去掉 display:block/marginLeft, 按钮置于文本末行右侧, 视觉更协调 — 小沈-2026-09-17
// 编辑历史: 2026-09-17 小沈 - 折叠按钮改为内联跟在文本末尾不另起新行: 去掉外层 flex div,
//   span display:inline + whiteSpace:nowrap 直接跟在 shown 文本流末尾(最后一行右侧尾巴) — 小沈-2026-09-17
// 编辑历史: 2026-10-05 小欧 - 折叠 state 与事件处理交公用 hook useDisclosure(文档[9] §5.7), 与 ThinkingStream 去重; 5 处调用行为零回归 — 小欧-2026-10-05
// 编辑历史: 2026-10-05 小欧 - 加可选 renderExpanded: 展开态渲染由调用方注入(左列 task 卡 response 传 MarkdownSlot);
//   不传则展开仍显纯文本, 折叠态与其余 4 处调用零变化 — 小欧-2026-10-05
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

import React, { useMemo } from 'react';
import { CircleArrow } from '@/components/CircleArrow';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
// 2026-10-05 小欧 - 折叠状态交公用 hook(文档[9] §5.7): 与 ThinkingStream 思考行共用,
//   原 onClick/onKeyDown 逻辑重复两处, 违 DRY/健壮性; 本组件 5 处调用行为零变化 — 小欧-2026-10-05
import { useDisclosure } from '@/features/chat/hooks/useDisclosure';

interface CollapsibleTextProps {
  text: string;
  maxLines?: number; // 默认 5 行阈值
  maxChars?: number; // 默认 200 字阈值
  /**
   * 2026-10-05 小欧 北京老陈指令(左列 task 卡 response 接 Markdown): **展开态**的渲染方式,
   *   由调用方注入(左列传入 MarkdownSlot 按排版渲染)。不传则保持原样(展开仍是纯文本全文),
   *   其余 4 处调用零变化。
   *   为何用"渲染策略注入"而不是把 expanded state 提到外面: 提state 需在 TaskListPanel 复刻
   *   阈值判定+首2行摘要+箭头 UI 约 30 行(违 DRY, 且 CollapsibleText 自 2026-08-28 起
   *   有 text 首100字符重置 expanded 等一整套状态机, 复制必漏)。本组件职责仍是"折叠/展开两态怎么显示",
   *   展开态内容属调用方 —— 本组件不需要知道 Markdown 是什么(SRP)。
   */
  renderExpanded?: (text: string) => React.ReactNode;
}

const CollapsibleText: React.FC<CollapsibleTextProps> = ({
  text,
  maxLines = 5,
  maxChars = 200,
  renderExpanded,
}) => {
  // 2026-10-05 小欧 - 折叠 state 交公用 hook(文档[9] §5.7), 替 ThinkingStream 复写同逻辑 — 小欧-2026-10-05
  const { expanded, setExpanded, onToggleClick, onToggleKeyDown } =
    useDisclosure(false);
  // 2026-09-03 小欧 修复: text变化(跨消息切换)时重置expanded, 用首100字符做key区分同消息内流式追加
  const _textKey = text.slice(0, 100);
  const _prevTextKeyRef = React.useRef(_textKey);
  React.useEffect(() => {
    if (_prevTextKeyRef.current !== _textKey) {
      setExpanded(false);
      _prevTextKeyRef.current = _textKey;
    }
  }, [_textKey, setExpanded]); // 2026-10-05 小欧: setExpanded 来自 useState 恒稳定, 列入依赖消 exhaustive-deps 告警(实际零重跑) — 小欧-2026-10-05
  const overflow = useMemo(() => {
    const lineCount = text.split('\n').length;
    return lineCount > maxLines || text.length > maxChars;
  }, [text, maxLines, maxChars]);

  const shown = useMemo(() => {
    // 展开态: 有注入渲染器则用它(左列 task 卡 response 走 Markdown), 否则原样显示全文
    if (!overflow || expanded) {
      return expanded && renderExpanded ? renderExpanded(text) : text;
    }
    const lines = text.split('\n');
    // 2026-08-27 小欧 修复: 多行内容优先取首2行摘要(BUG-G), 单行超长无换行才按字符截断(修复#7)
    if (lines.length > 1) {
      const preview = lines.slice(0, 2).join('\n');
      if (preview.length > maxChars) return preview.slice(0, maxChars) + '…';
      return preview;
    }
    if (text.length > maxChars) return text.slice(0, maxChars) + '…';
    return text;
  }, [text, overflow, expanded, maxChars, renderExpanded]);

  return (
    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {shown}
      {overflow && (
        <span
          role="button"
          tabIndex={0}
          aria-expanded={expanded}
          onClick={onToggleClick}
          onKeyDown={onToggleKeyDown}
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
