/**
 * WriteFileRenderer - writetext 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data.content_preview: string；
 *   llm_data.metrics: {bytes_written}；llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import WriteFileView from "../../views/WriteFileView";
import { BaseRendererProps } from "./BaseRendererProps";

interface WriteFileRendererProps extends BaseRendererProps {}

const WriteFileRenderer: React.FC<WriteFileRendererProps> = ({ step }) => {
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
    <WriteFileView
      data={{
        content_preview: (data.content_preview as string) || "",
      }}
      metrics={{
        bytes_written: (metrics.bytes_written as number) ?? 0,
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(WriteFileRenderer);
