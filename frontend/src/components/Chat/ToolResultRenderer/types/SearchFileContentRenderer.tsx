/**
 * SearchFileContentRenderer - grep 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   content模式: data.matches: Array<{file,line,matched,content,before?,after?}> + total_matches/total_files
 *   count模式: {total_matches,total_files}
 *   only_files模式: data.matches: Array<{file,lines:number[]}> + total_matches/total_files
 *   llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *   （不再使用 searchTransformers 旧转换）
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import SearchFileContentView from "../../views/SearchFileContentView";
import { BaseRendererProps } from "./BaseRendererProps";

interface SearchFileContentRendererProps extends BaseRendererProps {}

const SearchFileContentRenderer: React.FC<SearchFileContentRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  const matches = (data.matches as Array<Record<string, unknown>>) || [];
  const onlyFiles = matches.length > 0
    ? Array.isArray((matches[0] as Record<string, unknown>).lines)
    : false;

  return (
    <SearchFileContentView
      data={{
        mode: onlyFiles ? "only_files" : (matches.length > 0 ? "content" : "count"),
        matches,
        total_matches: (data.total_matches as number) ?? 0,
        total_files: (data.total_files as number) ?? 0,
        skipped_binary_files: (data.skipped_binary_files as string[]) || undefined,
        skipped_binary_count: (data.skipped_binary_count as number) ?? undefined,
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(SearchFileContentRenderer);
