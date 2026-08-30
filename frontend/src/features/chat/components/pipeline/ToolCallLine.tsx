// 编辑历史: 2026-08-26 小欧 - 修复B1: 观察摘要优先tool_result(4.9.3),兜底summary/content
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 删tool_params误用(8)/摘要tool_result优先(9)/展开渲染tool_result优先(10)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P0-1/去框-P0-4: margin6px0→8px0; 常态去radius改borderLeft2px#e8e8e8左线分态(highlight才#faad14+radius6); 主色#1890ff→#1677ff
// 编辑历史: 2026-08-27 小欧 - 修复chat-C: 新契约 tool_result 数组取首项 summary/llm_data.summary, 不再回落字面量[工具结果]
// 编辑历史: 2026-08-28 小强 - 修复[21]: getObsSummary空数组回落丢失, parts为空时fallback到o.summary/content - 小强-2026-08-28
// 编辑历史: 2026-08-28 小强 - 修复[22]: tool_result含空数组走错分支, 改条件为数组且长度>0 - 小强-2026-08-28
// 编辑历史: 2026-08-28 小欧 - ④A/a2: 高亮1px→2px + WARNING_BG令牌化, 左线统一2px
// 编辑历史: 2026-08-29 小强 - 修复#22: 展开观察区支持字符串tool_result渲染(与数组/兜底content并列) - 小强-2026-08-29
// 编辑历史: 2026-08-30 小欧 - 第十三章13.10.3.1+13.10.4(设计文档[2]13.12.6, 北京老陈 2026-08-30 批准): 全文件魔法数字收敛——margin(MD)/padding(XS·MD组合=4/8/4/10)/marginLeft(SM)/展开区 marginTop(XS)+paddingLeft(LG)+marginBottom(XS)/观察块 marginTop(XS) 全部落 Spacing; 常态去掉自带左线(borderLeft=undefined, 去双线, 流水线容器左线唯一), HITL 高亮态 THIN 黄线保留 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 折叠展开内(展开区 marginTop/参数标头 marginBottom/观察块 marginTop/观察标头 marginBottom)一律 Spacing.XS-2=2, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 间距统一收口: 工具行自身 margin Spacing.MD(8)→stepMargin(false)(=MD-2=6), 与思考/正文/状态 step 段距同值, 杜绝工具行与文本行段距不一致 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(字体留白全0 + 行高=字号+4): 根容器 lineHeight=字号+Spacing.XS(4) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案: 字体留白全0 / step间6(SM) / step内文字4(XS折不折同) / obs标签4(XS) / 段内折不折2(XS-2): 观察块间4 标签4 段内2，工具行段距 SM6 - 小欧-2026-08-30
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
import type { ExecutionStep } from '../../../../types/execution';
import { CollapsibleText } from './CollapsibleText';
import ToolResultRenderer from '../ToolResultRenderer';
import { Colors, BorderWidth, Spacing, stepMargin } from '@/utils/stepStyles';

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
  // 2026-08-27 小欧 三堂会审: action步骤无tool_params, 参数正确来源为tools[0].params
  const params = action.tools?.[0]?.params ?? {};
  const paramText = JSON.stringify(params);
  const toolName = tools.map((t) => t.tool).join(', ');
  const obs0 = observations[0];
  // 编辑历史: 2026-08-27 小欧 修复: 新契约 tool_result 为数组时取首项真实摘要, 不再回落字面量'[工具结果]'(BUG-C)
  const getObsSummary = (o?: ExecutionStep): string => {
    const tr = o?.tool_result;
    if (tr != null) {
      if (typeof tr === 'string') return tr;
      if (Array.isArray(tr)) {
        const parts = tr
          .map((item) => {
            if (typeof item === 'string') return item;
            const obj = item as Record<string, unknown>;
            const llm = (obj.llm_data || obj.llmData) as
              | Record<string, unknown>
              | undefined;
            return (obj.summary as string) || (llm?.summary as string) || '';
          })
          .filter((s) => s);
        if (!parts.length)
          return (o?.summary as string) || (o?.content as string) || '';
        if (parts.length) return parts.join('; ');
      }
      return (o?.summary as string) || (o?.content as string) || '';
    }
    return (o?.summary as string) || (o?.content as string) || '';
  };
  const obsSummary = getObsSummary(obs0);
  const retryCount = action.action_retry_count;
  const attemptLabel =
    retryCount != null && retryCount > 0 ? `(重试${retryCount})` : '';

  return (
    <div
      className={highlight ? 'hitl-border' : undefined}
      style={{
        fontSize: 13,
        color: Colors.TEXT.PRIMARY,
        lineHeight: `${13 + Spacing.XS}px`,
        margin: stepMargin(false),
        padding: `${Spacing.XS}px ${Spacing.SM}px ${Spacing.XS}px ${Spacing.XS + Spacing.SM}px`, // 4/6/4/10
        borderRadius: highlight ? 6 : 0,
        // 13.10.4: 常态去掉自带左线(去双线, 容器总轴线唯一); HITL 高亮态 THIN 黄线保留
        borderLeft: highlight
          ? `${BorderWidth.THIN}px solid ${Colors.WARNING}`
          : undefined,
        background: highlight ? Colors.WARNING_BG : 'transparent',
      }}
    >
      <span style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)}>
        🔧 {toolName} {attemptLabel}
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          {' '}
          参数：{paramText.slice(0, 60)}
          {paramText.length > 60 ? '…' : ''}
        </span>
        {obsSummary && (
          <span style={{ color: Colors.SUCCESS }}>
            {' '}
            → {obsSummary.slice(0, 40)}
          </span>
        )}
        <span style={{ marginLeft: Spacing.SM, color: Colors.PRIMARY }}>
          {open ? '▲' : '▼'}
        </span>
      </span>
      {open && (
        <div style={{ marginTop: Spacing.XS - 2, paddingLeft: Spacing.LG }}>
          {' '}
          {/* 展开区 2=XS-2 */}
          <div
            style={{
              color: Colors.TEXT.SECONDARY,
              lineHeight: `${13 + Spacing.XS}px`,
              marginBottom: Spacing.XS,
            }}
          >
            参数：
          </div>
          <CollapsibleText text={paramText} />
          {observations.map((o, idx) => (
            <div key={idx} style={{ marginTop: Spacing.XS }}>
              {' '}
              {/* 观察块间 4=XS */}
              <div
                style={{
                  color: Colors.TEXT.SECONDARY,
                  lineHeight: `${13 + Spacing.XS}px`,
                  marginBottom: Spacing.XS,
                }}
              >
                观察{observations.length > 1 ? ` ${idx + 1}` : ''}：
              </div>
              {/* 2026-08-27 小欧 三堂会审: 富渲染tool_result可达, 有tool_result走ToolResultRenderer否则纯文本 */}
              {Array.isArray(o.tool_result) && o.tool_result.length > 0 ? (
                <ToolResultRenderer step={o} />
              ) : typeof o.tool_result === 'string' ? (
                <CollapsibleText text={o.tool_result} />
              ) : (
                <CollapsibleText text={o.content ?? ''} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { ToolCallLine };
