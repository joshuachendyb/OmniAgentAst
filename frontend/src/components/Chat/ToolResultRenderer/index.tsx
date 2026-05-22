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
import TimeNowRenderer from './types/TimeNowRenderer';
import TimeFormatRenderer from './types/TimeFormatRenderer';
import TimeDiffRenderer from './types/TimeDiffRenderer';
import TimerSetRenderer from './types/TimerSetRenderer';
import TimerClearRenderer from './types/TimerClearRenderer';
import TimeUtcToLocalRenderer from './types/TimeUtcToLocalRenderer';
import TimeLocalToUtcRenderer from './types/TimeLocalToUtcRenderer';
import TimeIsWeekendRenderer from './types/TimeIsWeekendRenderer';
import TimeIsHolidayRenderer from './types/TimeIsHolidayRenderer';
import TimeAddRenderer from './types/TimeAddRenderer';
import TimeCompareRenderer from './types/TimeCompareRenderer';
import TimeIsWorkdayRenderer from './types/TimeIsWorkdayRenderer';
import TimeNextNWorkdayRenderer from './types/TimeNextNWorkdayRenderer';
import TimeToTimestampRenderer from './types/TimeToTimestampRenderer';
import TimestampToTimeRenderer from './types/TimestampToTimeRenderer';
import TimerListRenderer from './types/TimerListRenderer';
import FileOperationRenderer from './types/FileOperationRenderer';
import FileMonitorRenderer from './types/FileMonitorRenderer';
import FileStatisticsRenderer from './types/FileStatisticsRenderer';
import FileChecksumRenderer from './types/FileChecksumRenderer';
import GetDirectoryTreeRenderer from './types/GetDirectoryTreeRenderer';
import DefaultRenderer from './types/DefaultRenderer';
import { BaseRendererProps } from './types/BaseRendererProps';

interface ToolResultRendererProps extends BaseRendererProps {
  toggleExpand?: (index: number) => void;
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
    case "read_text_file":
    case "read_file":
      return <ReadFileRenderer step={step} />;
    case "write_text_file":
    case "write_file":
      return <WriteFileRenderer step={step} />;
    case "delete_file":
      return <DeleteFileRenderer step={step} />;
    case "move_file":
      return <MoveFileRenderer step={step} />;
    case "search_files":
      return <SearchFilesRenderer step={step} />;
    case "grep_file_content":
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
    case "get_current_time":
    case "time_now":
      return <TimeNowRenderer step={step} />;
    case "time_format":
      return <TimeFormatRenderer step={step} />;
    case "time_diff":
      return <TimeDiffRenderer step={step} />;
    case "timer_set":
      return <TimerSetRenderer step={step} />;
    case "timer_clear":
      return <TimerClearRenderer step={step} />;
    case "time_utc_to_local":
      return <TimeUtcToLocalRenderer step={step} />;
    case "time_local_to_utc":
      return <TimeLocalToUtcRenderer step={step} />;
    case "time_is_weekend":
      return <TimeIsWeekendRenderer step={step} />;
    case "time_is_holiday":
      return <TimeIsHolidayRenderer step={step} />;
    case "time_add":
      return <TimeAddRenderer step={step} />;
    case "time_compare":
      return <TimeCompareRenderer step={step} />;
    case "time_is_workday":
      return <TimeIsWorkdayRenderer step={step} />;
    case "time_next_n_workday":
      return <TimeNextNWorkdayRenderer step={step} />;
    case "time_to_timestamp":
      return <TimeToTimestampRenderer step={step} />;
    case "timestamp_to_time":
      return <TimestampToTimeRenderer step={step} />;
    case "timer_list":
      return <TimerListRenderer step={step} />;
    case "file_monitor":
      return <FileMonitorRenderer step={step} />;
    case "file_statistics":
      return <FileStatisticsRenderer step={step} />;
    case "file_checksum":
      return <FileChecksumRenderer step={step} />;
    case "edit_text_file":
    case "rename_file":
    case "list_allowed_directories":
    case "read_media_file":
    case "read_batch_file":
    case "precise_replace_in_file":
    case "get_file_hash":
    case "extract_archive":
      return <FileOperationRenderer step={step} />;
    case "get_directory_tree":
      return <GetDirectoryTreeRenderer step={step} />;
    default:
      return <DefaultRenderer step={step} />;
  }
};

export default React.memo(ToolResultRenderer);
