/**
 * FileStatisticsRenderer - file_statistics 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用FileStatisticsView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import FileStatisticsView from "../../views/FileStatisticsView";
import { BaseRendererProps } from "./BaseRendererProps";

interface FileStatisticsRendererProps extends BaseRendererProps {}

const FileStatisticsRenderer: React.FC<FileStatisticsRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 统计数据为空
      </div>
    );
  }

  return <FileStatisticsView data={data} />;
};

export default React.memo(FileStatisticsRenderer);