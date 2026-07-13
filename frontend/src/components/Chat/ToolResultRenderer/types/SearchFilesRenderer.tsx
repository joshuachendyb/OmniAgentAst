/**
 * SearchFilesRenderer - find 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data.matches: Array<{name,path,relative_path,type,size?}>，data.total_matches?；
 *   llm_data.metrics: {total}；llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *   （不再使用 searchTransformers 旧转换）
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import SearchFilesView from "../../views/SearchFilesView";
import { BaseRendererProps } from "./BaseRendererProps";

interface SearchFilesRendererProps extends BaseRendererProps {}

const SearchFilesRenderer: React.FC<SearchFilesRendererProps> = ({ step }) => {
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
    <SearchFilesView
      data={{
        matches: (data.matches as Array<Record<string, unknown>>) || [],
        total_matches: (data.total_matches as number) ?? (metrics.total as number) ?? 0,
      }}
      metrics={{ total: (metrics.total as number) ?? 0 }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(SearchFilesRenderer);
