/**
 * StepFooter组件 - 步骤底部（状态、分页、工具信息）
 * 
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 * @update 2026-04-28 小强 - 第十一步：边界情况处理（无内容时完全隐藏）
 */

import React from "react";
import type { ExecutionStep } from "../../../utils/sse";

interface StepFooterProps {
  step: ExecutionStep;
  hasMore: boolean;
  onLoadMore: () => void;
}

/**
 * StepFooter组件
 * 显示执行状态、耗时、重试次数、摘要、加载更多
 * 第十一步：边界情况处理 - 无内容时完全隐藏
 */
const StepFooter: React.FC<StepFooterProps> = ({
  step,
  hasMore,
  onLoadMore,
}) => {
  const execution_status = step.execution_status;
  const execution_time_ms = step.execution_time_ms;
  const action_retry_count = step.action_retry_count;
  const summary = step.summary;
  const error_message = step.error_message;

  // 第十一步：边界情况处理 - 检查是否有内容需要显示
  const hasContent = execution_status || hasMore || summary || error_message;

  if (!hasContent) {
    return null;
  }

  return (
    <>
      {/* 加载更多按钮 */}
      {hasMore && (
        <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
          <span 
            onClick={onLoadMore}
            style={{ 
              cursor: "pointer", 
              color: "#1890ff",
              textDecoration: "underline",
              fontWeight: 500,
              transition: "all 0.2s ease",
            }}
          >
            加载更多
          </span>
        </div>
      )}

      {/* 执行状态信息 */}
      {execution_status && (
        <div style={{ marginTop: 6, fontSize: 12 }}>
          <span style={{ 
            color: execution_status === "success" ? "#52c41a" : "#ff4d4f",
            fontWeight: 500 
          }}>
            {execution_status === "success" ? "✅ 成功" : "❌ 失败"}
          </span>
          
          {/* 执行耗时 */}
          {execution_time_ms !== undefined && execution_time_ms > 0 && (
            <span style={{ color: "#666", marginLeft: 8 }}>
              | ⏱️ 耗时：{(() => {
                if (!execution_time_ms || execution_time_ms <= 0) return "";
                if (execution_time_ms < 1000) return `${execution_time_ms}ms`;
                return `${(execution_time_ms / 1000).toFixed(1)}s`;
              })()}
            </span>
          )}
          
          {/* 重试次数 */}
          {action_retry_count !== undefined && action_retry_count > 0 && (
            <span style={{ color: "#faad14", marginLeft: 8 }}>
              | 🔄 重试：{action_retry_count}次
            </span>
          )}
          
          {/* 摘要 */}
          {summary && (
            <span style={{ color: "#666", marginLeft: 8 }}>
              | 📝 {summary}
            </span>
          )}
          
          {/* 错误信息 */}
          {error_message && (
            <span style={{ color: "#ff4d4f", marginLeft: 8 }}>
              | ❌ {error_message}
            </span>
          )}
        </div>
      )}
    </>
  );
};

export default React.memo(StepFooter);
