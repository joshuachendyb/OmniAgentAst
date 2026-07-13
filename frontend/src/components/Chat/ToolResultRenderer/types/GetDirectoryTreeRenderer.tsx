/**
 * GetDirectoryTreeRenderer - tree 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data: { tree: {name,path,type,children:[]}, statistics: {file_count,dir_count,total_size} }
 *   llm_data.summary。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小健
 * @version 2.0.0
 * @since 2026-05-11
 */

import React from "react";
import GetDirectoryTreeView from "../../views/GetDirectoryTreeView";
import { BaseRendererProps } from "./BaseRendererProps";

interface GetDirectoryTreeRendererProps extends BaseRendererProps {}

const GetDirectoryTreeRenderer: React.FC<GetDirectoryTreeRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  const statistics = (data.statistics || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";
  const tree = (data.tree as Record<string, unknown>) || null;

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return (
    <GetDirectoryTreeView
      data={{
        tree,
        statistics: {
          file_count: (statistics.file_count as number) ?? 0,
          dir_count: (statistics.dir_count as number) ?? 0,
          total_size: (statistics.total_size as number) ?? 0,
        },
      }}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(GetDirectoryTreeRenderer);
