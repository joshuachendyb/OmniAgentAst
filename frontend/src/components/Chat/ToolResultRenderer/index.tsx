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
// 【北京老陈 2026-07-13 小欧】switch 必须按后端注册名路由(后端 Phase1 v6.0 已将工具名精简为短名:
//   listdir/readtext/writetext/readmedia/edittext/tree/find/grep/compress/extract/move/copy/delete/rename
//   timenow/timeadd/timediff/timer_set/timer_clear/timer_list)，旧长名(copy_file/list_directory...)已全部 miss 落到 DefaultRenderer。
import ListDirectoryRenderer from './types/ListDirectoryRenderer';
import ReadFileRenderer from './types/ReadFileRenderer';
import WriteFileRenderer from './types/WriteFileRenderer';
import DeleteFileRenderer from './types/DeleteFileRenderer';
import MoveFileRenderer from './types/MoveFileRenderer';
import SearchFilesRenderer from './types/SearchFilesRenderer';
import SearchFileContentRenderer from './types/SearchFileContentRenderer';
import CopyFileRenderer from './types/CopyFileRenderer';
import CompressFilesRenderer from './types/CompressFilesRenderer';
import TimeNowRenderer from './types/TimeNowRenderer';
import TimeDiffRenderer from './types/TimeDiffRenderer';
import TimerSetRenderer from './types/TimerSetRenderer';
import TimerClearRenderer from './types/TimerClearRenderer';
import TimeAddRenderer from './types/TimeAddRenderer';
import TimerListRenderer from './types/TimerListRenderer';
import FileOperationRenderer from './types/FileOperationRenderer';
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

  // 工厂模式：根据后端注册名(tool_name)选择渲染器 — 小欧 2026-07-13 统一为后端真实短名
  switch (step.tool_name) {
    // ===== 文件工具（后端注册名）=====
    case "listdir":
      return <ListDirectoryRenderer step={step} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "readtext":
    case "read_file":
      return <ReadFileRenderer step={step} />;
    case "writetext":
    case "write_file":
      return <WriteFileRenderer step={step} />;
    case "delete":
      return <DeleteFileRenderer step={step} />;
    case "move":
      return <MoveFileRenderer step={step} />;
    case "find":
      return <SearchFilesRenderer step={step} />;
    case "grep":
    case "grep_file_content":
    case "search_file_content":
      return <SearchFileContentRenderer step={step} />;
    case "copy":
      return <CopyFileRenderer step={step} />;
    case "compress":
      return <CompressFilesRenderer step={step} />;
    case "tree":
      return <GetDirectoryTreeRenderer step={step} />;
    case "edittext":
    case "rename":
    case "readmedia":
    case "extract":
      return <FileOperationRenderer step={step} />;
    // ===== 计时器工具 =====
    case "timer_set":
      return <TimerSetRenderer step={step} />;
    case "timer_clear":
      return <TimerClearRenderer step={step} />;
    case "timer_list":
      return <TimerListRenderer step={step} />;
    // ===== 时间工具（后端注册名）=====
    case "timenow":
    case "get_current_time":
      return <TimeNowRenderer step={step} />;
    case "timediff":
      return <TimeDiffRenderer step={step} />;
    case "timeadd":
      return <TimeAddRenderer step={step} />;
    default:
      return <DefaultRenderer step={step} />;
  }
};

export default React.memo(ToolResultRenderer);
