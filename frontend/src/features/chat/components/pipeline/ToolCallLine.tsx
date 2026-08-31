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
// 编辑历史: 2026-09-01 小欧 - 工具观察按工具维度组织: 单/多统一结构, 第一行集合名+同行工具名列表, 内层每工具子行(独立参数+状态+摘要, 按索引与tool_result配对); 修多工具只显首项结果; 修参数结果挤一行 - 小欧-2026-09-01
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
  // 单 observation step 的 tool_result 数组，与 tools[] 按索引 1:1 配对（2026-09-01 小欧）
  const obsStep = observations[0];
  const results = (
    Array.isArray((obsStep as ExecutionStep | undefined)?.tool_result)
      ? ((obsStep as ExecutionStep).tool_result as unknown)
      : []
  ) as Array<Record<string, unknown>>;
  const isMulti = action.exec_type === 'multi';
  const toolCount = tools.length;
  const collectionLabel = isMulti
    ? `并行 ${toolCount} 个工具`
    : `调用 1 个工具`;
  const toolNameList = tools.map((t) => t.tool).join(', ');
  const firstLine = `${collectionLabel}  [${toolNameList}]`;
  // 展开区完整参数：全部工具的 params 汇总（2026-09-01 小欧）
  const paramText = JSON.stringify(tools.map((t) => t.params ?? {}));
  // 每工具结果摘要 + 状态（按索引 i 取，杜绝只取首项）（2026-09-01 小欧）
  // 三堂会审(2026-09-01): 保留旧 getObsSummary 摘要容错(llm_data.summary→data_text→summary→兜底'-'), 防关联退化
  const getResultSummary = (i: number): string => {
    const r = results[i];
    if (!r) return '';
    const llm = (r.llm_data || r.llmData) as
      | Record<string, unknown>
      | undefined;
    return (
      (llm?.summary as string) ||
      (r.data_text as string) ||
      (r.summary as string) ||
      ''
    );
  };
  const getResultStatus = (
    i: number
  ): 'success' | 'error' | 'warning' | undefined => {
    const r = results[i];
    if (!r) return undefined;
    const llm = (r.llm_data || r.llmData) as
      | Record<string, unknown>
      | undefined;
    const status = (llm?.status || {}) as Record<string, unknown>;
    const code = status.exec_code as string;
    return ['success', 'error', 'warning'].includes(code)
      ? (code as 'success' | 'error' | 'warning')
      : undefined;
  };
  const retryCount = action.action_retry_count;
  const attemptLabel =
    retryCount != null && retryCount > 0 ? `(重试${retryCount})` : '';
  const statusColorMap = {
    success: Colors.SUCCESS,
    error: Colors.ERROR,
    warning: Colors.WARNING,
  } as const;
  const statusIconMap = { success: '✔', error: '✖', warning: '⚠' } as const;

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
        🔧 {firstLine} {attemptLabel}
        <span style={{ marginLeft: Spacing.SM, color: Colors.PRIMARY }}>
          {open ? '▲' : '▼'}
        </span>
      </span>
      {/* 每工具子行：工具名+参数一行，→结果独立一行缩进（2026-09-01 小欧） */}
      {/* 间距遵循 stepStyles 既有 observation 风格(2026-08-30 定案): 字号 13(与展开区统一, 非12), 行高=字号13+Spacing.XS, 段内折不折=Spacing.XS-2, 间距一律 Spacing 常量派生 */}
      <div style={{ marginTop: Spacing.XS }}>
        {tools.map((t, i) => {
          const tParamText = JSON.stringify(t.params ?? {});
          const sum = getResultSummary(i);
          const st = getResultStatus(i);
          // 三堂会审(2026-09-01): 状态缺失时用中性文字色、不显图标, 防误报成功
          const color = st ? statusColorMap[st] : Colors.TEXT.PRIMARY;
          const icon = st ? `${statusIconMap[st]} ` : '';
          const isLast = i === tools.length - 1;
          const branch = isLast ? '└─' : '├─';
          const sub = isLast ? '   ' : '│  ';
          return (
            <div
              key={i}
              style={{ marginTop: Spacing.XS, paddingLeft: Spacing.SM }}
            >
              <div
                style={{
                  fontSize: 13,
                  lineHeight: `${13 + Spacing.XS}px`,
                  color: Colors.TEXT.PRIMARY,
                }}
              >
                {branch} {t.tool}{' '}
                <span style={{ color: Colors.TEXT.SECONDARY }}>
                  参数：{tParamText.slice(0, 60)}
                  {tParamText.length > 60 ? '…' : ''}
                </span>
              </div>
              {sum && (
                <div
                  style={{
                    marginTop: Spacing.XS - 2 /* 段内折不折 2=XS-2 */,
                    paddingLeft: Spacing.SM,
                    lineHeight: `${13 + Spacing.XS}px`,
                    color,
                    fontSize: 13,
                  }}
                >
                  {sub} {icon}
                  {sum.slice(0, 60)}
                </div>
              )}
            </div>
          );
        })}
      </div>
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
          {tools.map((t, i) => {
            // 单工具完整结果：构造仅含该工具 tool_result 的临时 step 交给 ToolResultRenderer
            const singleResult = results[i] ? [results[i]] : [];
            const singleStep = {
              ...(obsStep as ExecutionStep),
              tool_result: singleResult,
            };
            return (
              <div key={i} style={{ marginTop: Spacing.XS }}>
                <div
                  style={{
                    color: Colors.TEXT.SECONDARY,
                    lineHeight: `${13 + Spacing.XS}px`,
                    marginBottom: Spacing.XS,
                  }}
                >
                  {t.tool} 结果：
                </div>
                {singleResult.length > 0 ? (
                  <ToolResultRenderer step={singleStep} />
                ) : (
                  <CollapsibleText text={obsStep?.content ?? ''} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export { ToolCallLine };
