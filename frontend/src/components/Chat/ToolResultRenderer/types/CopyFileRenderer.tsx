/**
 * CopyFileRenderer - copy 工具结果渲染器
 *
 * 从 ExecutionStep 提取数据并调用 CopyFileView 渲染。
 * 【北京老陈 2026-07-13 小欧】后端返回 {data, llm_data, other_data}：
 *   data={source_size, mtime}，目标大小在 llm_data.metrics.bytes，摘要在 llm_data.summary；
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小强
 * @version 1.0.1
 * @since 2026-04-25
 */

import React from "react";
import CopyFileView from "../../views/CopyFileView";
import { BaseRendererProps } from "./BaseRendererProps";

interface CopyFileRendererProps extends BaseRendererProps {}

const CopyFileRenderer: React.FC<CopyFileRendererProps> = ({ step }) => {
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
        ⚠️ 复制操作数据为空
      </div>
    );
  }

  return (
    <CopyFileView
      data={{
        source_size: data.source_size as number | null,
        mtime: data.mtime as number | null,
        dest_size: metrics.bytes as number | null,
        summary,
      }}
      success={success}
    />
  );
};

export default React.memo(CopyFileRenderer);
