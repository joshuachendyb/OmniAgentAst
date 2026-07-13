/**
 * ListDirectoryRenderer - listdir 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   execution_result = { data, llm_data, other_data }；
 *   data.entries: Array<{name,type,mtime,size?}>，data.truncated: bool；
 *   llm_data.metrics: {total,dir_count,file_count,total_size}；
 *   llm_data.summary 如「列出目录成功: N项」；
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import ListDirectoryView from "../../views/ListDirectoryView";
import { BaseRendererProps } from "./BaseRendererProps";

interface ListDirectoryRendererProps extends BaseRendererProps {}

const ListDirectoryRenderer: React.FC<ListDirectoryRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";
  const truncated = Boolean(data.truncated);

  if (!data || !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return (
    <ListDirectoryView
      data={{ entries: (data.entries as Array<Record<string, unknown>>) || [], truncated }}
      metrics={{
        total: (metrics.total as number) ?? 0,
        dir_count: (metrics.dir_count as number) ?? 0,
        file_count: (metrics.file_count as number) ?? 0,
        total_size: (metrics.total_size as number) ?? 0,
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(ListDirectoryRenderer);
