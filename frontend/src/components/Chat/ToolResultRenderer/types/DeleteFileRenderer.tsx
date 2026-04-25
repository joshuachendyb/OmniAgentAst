/**
 * DeleteFileRenderer - delete_file 工具结果渲染�? * 
 * 从ExecutionStep提取数据并调用DeleteFileView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";

import DeleteFileView from "../../views/DeleteFileView";
import { BaseRendererProps } from "./BaseRendererProps";

interface DeleteFileRendererProps extends BaseRendererProps {}

const DeleteFileRenderer: React.FC<DeleteFileRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return null;
  }

  return <DeleteFileView data={data} />;
};

export default React.memo(DeleteFileRenderer);
