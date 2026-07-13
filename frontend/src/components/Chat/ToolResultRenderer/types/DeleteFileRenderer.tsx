/**
 * DeleteFileRenderer - delete 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空；llm_data.metrics: {mode|status}；llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import DeleteFileView from "../../views/DeleteFileView";
import { BaseRendererProps } from "./BaseRendererProps";

interface DeleteFileRendererProps extends BaseRendererProps {}

const DeleteFileRenderer: React.FC<DeleteFileRendererProps> = ({ step }) => {
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
    <DeleteFileView
      metrics={{
        mode: (metrics.mode as string) || "",
        status: (metrics.status as string) || "",
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(DeleteFileRenderer);
