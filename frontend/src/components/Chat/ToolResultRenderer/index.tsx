/**
 * ToolResultRenderer组件 - 工具结果渲染器（工厂模式）
 * 
 * 根据tool_name选择对应的渲染器组件
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from 'react';
import type { ExecutionStep } from '../../../utils/sse';
import ListDirectoryView from '../views/ListDirectoryView';
import ReadFileView from '../views/ReadFileView';
import WriteFileView from '../views/WriteFileView';
import DeleteFileView from '../views/DeleteFileView';
import MoveFileView from '../views/MoveFileView';
import SearchFilesView from '../views/SearchFilesView';
import SearchFileContentView from '../views/SearchFileContentView';
import GenerateReportView from '../views/GenerateReportView';
import { transformSearchFilesData, transformSearchFileContentData } from '../../../utils/searchTransformers';

interface ToolResultRendererProps {
  step: ExecutionStep;
  isExpanded?: boolean;
  toggleExpand?: (index: number) => void;
  stepIndex?: number;
}

/**
 * 工具结果渲染器 - 工厂模式
 */
const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({
  step,
  isExpanded = true,
  toggleExpand,
  stepIndex,
}) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;
  if (!data) return null;

  const handleToggle = toggleExpand && stepIndex !== undefined 
    ? () => toggleExpand(stepIndex) 
    : undefined;

  // 工厂模式：根据tool_name选择渲染器
  switch (step.tool_name) {
    case "list_directory":
      return <ListDirectoryView data={data} toolParams={step.tool_params} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "read_file":
      return <ReadFileView data={data} />;
    case "write_file":
      return <WriteFileView data={data} />;
    case "delete_file":
      return <DeleteFileView data={data} />;
    case "move_file":
      return <MoveFileView data={data} />;
    case "search_files": {
      const transformedSearchFilesData = transformSearchFilesData(data);
      return <SearchFilesView data={transformedSearchFilesData} />;
    }
    case "search_file_content": {
      const transformedSearchFileContentData = transformSearchFileContentData(data);
      return <SearchFileContentView data={transformedSearchFileContentData} />;
    }
    case "generate_report":
      return <GenerateReportView data={data} isExpanded={isExpanded} onToggle={handleToggle} />;
    default:
      // 未知工具，显示原始JSON
      return (
        <pre style={{
          background: "#f5f5f5",
          padding: "10px",
          borderRadius: 4,
          fontSize: 12,
          maxHeight: 300,
          overflow: "auto",
        }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
};

export default React.memo(ToolResultRenderer);
