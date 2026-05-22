/**
 * FileChecksumRenderer - file_checksum 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用FileChecksumView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import FileChecksumView from "../../views/FileChecksumView";
import { BaseRendererProps } from "./BaseRendererProps";

interface FileChecksumRendererProps extends BaseRendererProps {}

const FileChecksumRenderer: React.FC<FileChecksumRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 校验和数据为空
      </div>
    );
  }

  return <FileChecksumView data={data} />;
};

export default React.memo(FileChecksumRenderer);