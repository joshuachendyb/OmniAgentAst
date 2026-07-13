/**
 * ReadFileRenderer - readtext 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data.content: string（带行号），data.truncated_lines?: int；
 *   llm_data.metrics: {lines,total_lines,bytes}；llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import ReadFileView from "../../views/ReadFileView";
import { BaseRendererProps } from "./BaseRendererProps";

interface ReadFileRendererProps extends BaseRendererProps {}

const ReadFileRenderer: React.FC<ReadFileRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return (
    <ReadFileView
      data={{
        content: (data.content as string) || "",
        truncated_lines: (data.truncated_lines as number) ?? undefined,
      }}
      metrics={{
        lines: (metrics.lines as number) ?? 0,
        total_lines: (metrics.total_lines as number) ?? 0,
        bytes: (metrics.bytes as number) ?? 0,
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(ReadFileRenderer);
