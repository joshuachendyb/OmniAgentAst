/**
 * TimeDiffRenderer - timediff 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空；llm_data.metrics: {seconds,days}；llm_data.summary 含中文相对描述。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-26
 */

import React from "react";
import TimeDiffView from "../../views/TimeDiffView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeDiffRendererProps extends BaseRendererProps {}

const TimeDiffRenderer: React.FC<TimeDiffRendererProps> = ({ step }) => {
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
    <TimeDiffView
      metrics={{ seconds: (metrics.seconds as number) ?? 0, days: (metrics.days as number) ?? 0 }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(TimeDiffRenderer);
