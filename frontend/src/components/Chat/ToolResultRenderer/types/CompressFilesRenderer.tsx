/**
 * CompressFilesRenderer - compress 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data: { compression_level, encrypted, original_size, compression_ratio }
 *   llm_data.metrics: { file_count, compressed_size, ratio, format }
 *   llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-25
 */

import React from "react";

import CompressFilesView from "../../views/CompressFilesView";
import { BaseRendererProps } from "./BaseRendererProps";

interface CompressFilesRendererProps extends BaseRendererProps {}

const CompressFilesRenderer: React.FC<CompressFilesRendererProps> = ({ step }) => {
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
    <CompressFilesView
      data={{
        compression_level: (data.compression_level as number) ?? 0,
        encrypted: Boolean(data.encrypted),
        original_size: (data.original_size as number) ?? 0,
        compression_ratio: (data.compression_ratio as number) ?? (metrics.ratio as number) ?? 0,
      }}
      metrics={{
        file_count: (metrics.file_count as number) ?? 0,
        compressed_size: (metrics.compressed_size as number) ?? 0,
        ratio: (metrics.ratio as number) ?? 0,
        format: (metrics.format as string) || "",
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(CompressFilesRenderer);
