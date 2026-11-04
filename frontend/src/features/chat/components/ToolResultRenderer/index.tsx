// 编辑历史: 2026-08-27 小欧 - 重构: 删36套per-tool视图与switch, 改按结果类型(tree/code/generic)分派(铁规复用优先/禁backward/KISS)
// 编辑历史: 2026-10-04 小欧 - 文档[8]第六章第1/2/4条: 删形状分派(树渲染器要的data永远拿不到+metrics是对象按number用失效+分派依据只取tr[0])
// 编辑历史: 2026-10-04 小欧 - 文档[8]§5.3 方法二(北京老陈裁定B案): 展开区只展示"结论"——头部状态点+完整摘要, 尾部metrics小标签;
//   data_text/tool_name/action/status.code·detail·hint/duration_ms/other_data 全部不显示(结果正文由 assistant 回答承载) — 小欧 2026-10-04
// 编辑历史: 2026-10-11 小欧 - 失败原因可视化(北京老陈令): ①头部下补[详情]/[提示]两行, 取
//   status.detail/hint(原 2026-10-04 定案排除, 致失败只显"失败"二字, 无从判断原因;
//   实测 write 失败 detail 为"Python语法错误(第85行…)"被丢弃), 成功态二者空串故零变化;
//   ②metrics 标签行前置[时间]/[耗时](step.timestamp + llm_data.duration_ms) — 小欧-2026-10-11
// 编辑历史: 2026-10-13 小欧 - 北京老陈裁定「不许截断」: ★(StarOutlined)后的 summary 由**单行省略**改为**折行完整显示**。
//   原 overflow:hidden + textOverflow:ellipsis + whiteSpace:nowrap 会把长命令摘要(如 git show fa644f85 --stat …)
//   砍掉后半段并加省略号, 排查信息丢失; 与参数区/工具行口径统一。外层 alignItems:center→flex-start,
//   折成多行时 ★ 与首行对齐而非悬在整块垂直中间; span 补 minWidth:0 才不会被 flex 撑破 — 小欧-2026-10-13
/**
 * ToolResultRenderer - 工具结果"结论区"渲染器
 *
 * 取数: 只认 step.tool_result(唯一载体)。展开区由 ToolCallLine 按数组下标配对传入单个元素,
 *   故本组件只需渲染 tool_result[0]。
 * 渲染(仅两段, 令牌全部取自 utils/stepStyles, 不新增设计令牌):
 *   ① 头  状态点(exec_code 上色) + 完整摘要(FontWeight.MEDIUM, 单行 CSS 省略)
 *   ③ 尾  metrics 小标签排(只取契约里的 text 字段, 无 text 则取 value)
 *
 * @author 小欧
 * @since 2026-08-27
 */
import React from 'react';
import { StarOutlined } from '@ant-design/icons';
import {
  Colors,
  FontSize,
  FontWeight,
  Spacing,
  Radius,
} from '@/utils/stepStyles';
import type { ExecutionStep } from '../../../../types/execution';
import { formatTimeHMS } from '@/utils/time';

/** 2026-10-11 小欧 - 失败/警告补充说明行的标签前缀(北京老陈令) */
const tagLabel = (tag: string, text: string, color: string) => (
  <div style={{ fontSize: FontSize.SECONDARY, color, wordBreak: 'break-all' }}>
    <span style={{ color: Colors.TEXT.SECONDARY }}>[{tag}]: </span>
    {text}
  </div>
);

interface ToolResultRendererProps {
  step: ExecutionStep;
}

const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({ step }) => {
  const tr = step.tool_result;
  if (!Array.isArray(tr) || tr.length === 0) return null;
  const el = (tr[0] || {}) as Record<string, unknown>;
  const llmData = (el.llm_data || {}) as Record<string, unknown>;
  const summary = (llmData.summary as string) || '';
  const status = (llmData.status || {}) as Record<string, unknown>;
  // 2026-10-11 小欧(北京老陈令) - 展示 detail/hint: 原 2026-10-04 定案把 status.code·detail·hint
  //   全部排除, 失败时只剩"失败"二字, 无从判断原因(实测 write 失败 detail 载"Python语法错误(第85行…)"
  //   被丢弃)。成功态二者为空串, 故仅非空时渲染, 成功显示零变化。
  const detail = (status.detail as string) || '';
  const hint = (status.hint as string) || '';
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;
  const labels = Object.entries(metrics).map(([k, v]) => {
    const m = (v || {}) as { text?: unknown; value?: unknown };
    return `${k}: ${(m.text as string) ?? String(m.value ?? '')}`;
  });
  // 2026-10-11 小欧(北京老陈令) - 时间/耗时置于既有 metrics 标签之前, 便于一眼定位这次调用何时发生、多久
  const timeLabel = step.timestamp
    ? `时间: ${formatTimeHMS(step.timestamp)}`
    : '';
  const duration = llmData.duration_ms;
  const durLabel = typeof duration === 'number' ? `耗时: ${duration}ms` : '';
  const headLabels = [timeLabel, durLabel].filter(Boolean);

  return (
    <div style={{ marginTop: Spacing.XS }}>
      {summary && (
        // 2026-10-13 北京老陈裁定: ★ 后的摘要**不许截断**, 长了折行完整显示。
        //   原为单行省略(overflow:hidden + textOverflow:ellipsis + whiteSpace:nowrap),
        //   长命令摘要(如 git show fa644f85 --stat …)会被砍掉后半段并加省略号, 排查信息丢失;
        //   与参数区/工具行「不许截断」口径统一。flex item 折行需 minWidth:0 才不被 flex 撑破。
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: Spacing.SM,
          }}
        >
          {/* 2026-10-04 小欧 北京老陈定案: 状态点改"亮蓝五角星"(Colors.PRIMARY #1677ff)固定色,
              不用状态色(绿=成功会与子行水滴重复); 失败/警告语义由子行水滴图标承担 — 小欧 2026-10-04 */}
          <StarOutlined
            style={{
              color: Colors.PRIMARY,
              fontSize: FontSize.SECONDARY,
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              fontWeight: FontWeight.MEDIUM,
              color: Colors.TEXT.PRIMARY,
              minWidth: 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {summary}
          </span>
        </div>
      )}
      {detail && tagLabel('详情', detail, Colors.ERROR)}
      {hint && tagLabel('提示', hint, Colors.TEXT.SECONDARY)}
      {(headLabels.length > 0 || labels.length > 0) && (
        <div
          style={{
            display: 'flex',
            gap: Spacing.XS,
            flexWrap: 'wrap',
            marginTop: Spacing.XS,
          }}
        >
          {[...headLabels, ...labels].map((t) => (
            <span
              key={t}
              style={{
                fontSize: FontSize.SMALL,
                lineHeight: `${FontSize.SMALL + Spacing.XS}px`,
                color: Colors.TEXT.SECONDARY,
                border: `1px solid ${Colors.BORDER.VERTICAL}`,
                borderRadius: Radius.SM,
                padding: `0 ${Spacing.XS}px`,
              }}
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default React.memo(ToolResultRenderer);
