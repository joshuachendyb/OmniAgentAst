/**
 * TimerListRenderer - timer_list 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data.timers: Array<{timer_id,callback,created_at,trigger_at,status}>；
 *   llm_data.metrics: {count}；llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";
import TimerListView from "../../views/TimerListView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimerListRendererProps extends BaseRendererProps {}

const TimerListRenderer: React.FC<TimerListRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "8px 12px" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return (
    <TimerListView
      data={{ timers: (data.timers as Array<Record<string, unknown>>) || [] }}
      metrics={{ count: (metrics.count as number) ?? 0 }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(TimerListRenderer);
