/**
 * ToolResultRenderer组件 - 工具结果渲染器（工厂模式）
 * 
 * 根据tool_name选择对应的Renderer组件
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from 'react';
import type { ExecutionStep } from '../../../utils/sse';
import ListDirectoryRenderer from './types/ListDirectoryRenderer';
import ReadFileRenderer from './types/ReadFileRenderer';
import WriteFileRenderer from './types/WriteFileRenderer';
import DeleteFileRenderer from './types/DeleteFileRenderer';
import MoveFileRenderer from './types/MoveFileRenderer';
import SearchFilesRenderer from './types/SearchFilesRenderer';
import SearchFileContentRenderer from './types/SearchFileContentRenderer';
import GenerateReportRenderer from './types/GenerateReportRenderer';
import CopyFileRenderer from './types/CopyFileRenderer';
import CreateDirectoryRenderer from './types/CreateDirectoryRenderer';
import GetFileInfoRenderer from './types/GetFileInfoRenderer';
import CompareFilesRenderer from './types/CompareFilesRenderer';
import BatchRenameRenderer from './types/BatchRenameRenderer';
import CompressFilesRenderer from './types/CompressFilesRenderer';
import DefaultRenderer from './types/DefaultRenderer';

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
  const handleToggle = toggleExpand && stepIndex !== undefined 
    ? () => toggleExpand(stepIndex) 
    : undefined;

  // 工厂模式：根据tool_name选择渲染器
  switch (step.tool_name) {
    case "list_directory":
      return <ListDirectoryRenderer step={step} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "read_file":
      return <ReadFileRenderer step={step} />;
    case "write_file":
      return <WriteFileRenderer step={step} />;
    case "delete_file":
      return <DeleteFileRenderer step={step} />;
    case "move_file":
      return <MoveFileRenderer step={step} />;
    case "search_files":
      return <SearchFilesRenderer step={step} />;
    case "search_file_content":
      return <SearchFileContentRenderer step={step} />;
    case "generate_report":
      return <GenerateReportRenderer step={step} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "copy_file":
      return <CopyFileRenderer step={step} />;
    case "create_directory":
      return <CreateDirectoryRenderer step={step} />;
    case "get_file_info":
      return <GetFileInfoRenderer step={step} />;
    case "compare_files":
      return <CompareFilesRenderer step={step} />;
    case "batch_rename":
      return <BatchRenameRenderer step={step} />;
    case "compress_files":
      return <CompressFilesRenderer step={step} />;
    default:
      return <DefaultRenderer step={step} />;
  }
};

export default React.memo(ToolResultRenderer);
