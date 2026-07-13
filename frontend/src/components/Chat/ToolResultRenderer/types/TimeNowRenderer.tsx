/**
 * TimeNowRenderer - timenow 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空；llm_data.summary 如「获取当前时间成功:2026-07-13 15:04:05，Sunday」。
 *   时间结果全在 summary 中。成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-26
 */

import React from "react";
import TimeNowView from "../../views/TimeNowView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeNowRendererProps extends BaseRendererProps {}

const TimeNowRenderer: React.FC<TimeNowRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return <TimeNowView summary={summary} success={success} />;
};

export default React.memo(TimeNowRenderer);
