// 编辑历史: 2026-08-27 小欧 - 重构: 删36套per-tool视图与switch, 改按结果类型(tree/code/generic)分派(铁规复用优先/禁backward/KISS)
// 编辑历史: 2026-10-04 小欧 - 文档[8]第六章第1/2/4条: 删形状分派(树渲染器要的data永远拿不到+metrics是对象按number用失效+分派依据只取tr[0])
// 编辑历史: 2026-10-04 小欧 - 文档[8]§5.3 方法二(北京老陈裁定B案): 展开区只展示"结论"——头部状态点+完整摘要, 尾部metrics小标签;
//   data_text/tool_name/action/status.code·detail·hint/duration_ms/other_data 全部不显示(结果正文由 assistant 回答承载) — 小欧 2026-10-04
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

interface ToolResultRendererProps {
  step: ExecutionStep;
}

const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({ step }) => {
  const tr = step.tool_result;
  if (!Array.isArray(tr) || tr.length === 0) return null;
  const el = (tr[0] || {}) as Record<string, unknown>;
  const llmData = (el.llm_data || {}) as Record<string, unknown>;
  const summary = (llmData.summary as string) || '';
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;
  const labels = Object.entries(metrics).map(([k, v]) => {
    const m = (v || {}) as { text?: unknown; value?: unknown };
    return `${k}: ${(m.text as string) ?? String(m.value ?? '')}`;
  });

  return (
    <div style={{ marginTop: Spacing.XS }}>
      {summary && (
        <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.SM }}>
          {/* 2026-10-04 小欧 北京老陈定案: 状态点改"亮蓝五角星"(Colors.PRIMARY #1677ff)固定色,
              不用状态色(绿=成功会与子行水滴重复); 失败/警告语义由子行水滴图标承担 — 小欧 2026-10-04 */}
          <StarOutlined
            style={{ color: Colors.PRIMARY, fontSize: FontSize.SECONDARY }}
          />
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              fontWeight: FontWeight.MEDIUM,
              color: Colors.TEXT.PRIMARY,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {summary}
          </span>
        </div>
      )}
      {labels.length > 0 && (
        <div
          style={{
            display: 'flex',
            gap: Spacing.XS,
            flexWrap: 'wrap',
            marginTop: Spacing.XS,
          }}
        >
          {labels.map((t) => (
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
