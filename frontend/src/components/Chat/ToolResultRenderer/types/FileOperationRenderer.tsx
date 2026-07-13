/**
 * FileOperationRenderer - readmedia/extract/edittext/rename 通用结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   按 step.tool_name 分支：
 *     - readmedia: data={file_name,mime_type,base64_data}
 *     - extract:   data={output_dir,extracted_files,skipped_files,format,file_list}
 *     - edittext/rename: data 通常 {}（edittext 部分成功含 {diff}）
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-05-10
 */

import React from "react";
import FileOperationView from "../../views/FileOperationView";
import { BaseRendererProps } from "./BaseRendererProps";

interface FileOperationRendererProps extends BaseRendererProps {}

const FileOperationRenderer: React.FC<FileOperationRendererProps> = ({ step }) => {
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

  return (
    <FileOperationView
      tool_name={step.tool_name || ""}
      data={data}
      summary={summary}
      success={success}
    />
  );
};

export default React.memo(FileOperationRenderer);
