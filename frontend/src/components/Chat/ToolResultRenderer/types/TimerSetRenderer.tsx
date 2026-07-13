/**
 * TimerSetRenderer - timer_set 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data.trigger_at: string('%Y-%m-%d %H:%M:%S')；
 *   llm_data.metrics: {delay}；llm_data.summary 含 timer_id 与「X分钟后触发」。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-26
 */

import React from "react";
import TimerSetView from "../../views/TimerSetView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimerSetRendererProps extends BaseRendererProps {}

const TimerSetRenderer: React.FC<TimerSetRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return (
    <TimerSetView
      data={{ trigger_at: (data.trigger_at as string) || "" }}
      metrics={{ delay: (metrics.delay as number) ?? 0 }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(TimerSetRenderer);
