// 编辑历史: 2026-08-26 小欧 - 修复B1: 观察摘要优先tool_result(4.9.3),兜底summary/content
/**
 * ToolCallLine - 工具调用内联弱化行 + HITL 高亮边框
 *
 * 【小欧 2026-08-26 8.4.11】4.4.3 工具调用行内联弱化：工具名 + 参数摘要 + 结果摘要
 * 一行弱化(灰小字)，不再卡片包裹；点开展开 params/observation 详情；命中 HITL 挂起
 * 时整行呼吸边框(.hitl-border)。ToolResultRenderer 已去卡片边框(4.9.1③)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useState } from 'react';
import type { ExecutionStep } from '../../../utils/sse';
import { CollapsibleText } from './CollapsibleText';
import ToolResultRenderer from '../ToolResultRenderer';

interface ToolCallLineProps {
  action: ExecutionStep; // type=action
  observations?: ExecutionStep[]; // type=observation
  highlight?: boolean; // HITL 联动高亮
}

const ToolCallLine: React.FC<ToolCallLineProps> = ({
  action,
  observations = [],
  highlight = false,
}) => {
  const [open, setOpen] = useState(false);
  const tools = action.tools || [];
  const params =
    action.tool_params ||
    (action.tools && action.tools.length > 0
      ? action.tools[0].params
      : undefined) ||
    {};
  const paramText = JSON.stringify(params);
  const toolName = tools.map((t) => t.tool).join(', ');
  const obs0 = observations[0];
  // 优先 observation.summary，其次 obs.content(纯文本)，再次 tool_result(4.9.3 新字段)
  const obsSummary =
    obs0?.summary ||
    obs0?.content ||
    (obs0?.tool_result != null ? '[工具结果]' : '');
  const retryCount = action.action_retry_count;
  const attemptLabel =
    retryCount != null && retryCount > 0 ? `(重试${retryCount})` : '';

  return (
    <div
      className={highlight ? 'hitl-border' : undefined}
      style={{
        fontSize: 13,
        color: '#666',
        margin: '6px 0',
        padding: '4px 8px',
        borderRadius: 4,
        background: highlight ? 'rgba(250,173,20,0.08)' : 'transparent',
      }}
    >
      <span style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)}>
        🔧 {toolName} {attemptLabel}
        <span style={{ color: '#8c8c8c' }}>
          {' '}
          参数：{paramText.slice(0, 60)}
          {paramText.length > 60 ? '…' : ''}
        </span>
        {obsSummary && (
          <span style={{ color: '#52c41a' }}> → {obsSummary.slice(0, 40)}</span>
        )}
        <span style={{ marginLeft: 6, color: '#1890ff' }}>
          {open ? '▲' : '▼'}
        </span>
      </span>
      {open && (
        <div style={{ marginTop: 6, paddingLeft: 12 }}>
          <div style={{ color: '#8c8c8c', marginBottom: 4 }}>参数：</div>
          <CollapsibleText text={paramText} />
          {observations.map((o, idx) => (
            <div key={idx} style={{ marginTop: 4 }}>
              <div style={{ color: '#8c8c8c', marginBottom: 4 }}>
                观察{observations.length > 1 ? ` ${idx + 1}` : ''}：
              </div>
              {typeof o.content === 'string' ? (
                <CollapsibleText text={o.content} />
              ) : (
                <ToolResultRenderer step={o} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { ToolCallLine };
