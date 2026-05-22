/**
 * FileMonitorRenderer - file_monitor 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用FileMonitorView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import FileMonitorView from "../../views/FileMonitorView";
import { BaseRendererProps } from "./BaseRendererProps";

interface FileMonitorRendererProps extends BaseRendererProps {}

const FileMonitorRenderer: React.FC<FileMonitorRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 监控数据为空
      </div>
    );
  }

  return <FileMonitorView data={data} />;
};

export default React.memo(FileMonitorRenderer);