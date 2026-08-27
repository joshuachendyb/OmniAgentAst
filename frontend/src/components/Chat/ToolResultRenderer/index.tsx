// 编辑历史: 2026-08-26 小欧 - 修复B1: ToolResultRenderer优先读obsStep.tool_result(4.9.3/7.4⑦),兜底content/summary
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.5 CANONICAL归一+删不实注释+8.4.6 删早退DefaultRenderer走switch
// 编辑历史: 2026-08-27 小欧 - 三堂会审复核: 8.4.6删除早退经关联逻辑审查发现退化风险(后端08-18新契约data由data_text承载, 纯文本工具解析失败致专用渲染器渲染空), 据"严禁退化"铁规恢复早退tool_result→DefaultRenderer, 专用渲染器维持HEAD不可达状态(无退化)
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
// 【北京老陈 2026-07-13 小欧】switch 必须按后端注册名路由(后端已将工具名精简为短名)。
// 2026-08-27 小欧 三堂会审: 前端侧CANONICAL归一映射, 长名先归一为短名再路由(见下方常量)
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

// 2026-08-27 小欧 三堂会审: 前端侧CANONICAL归一映射, 长名先归一为短名再路由
const CANONICAL: Record<string, string> = {
  read_file: 'readtext',
  write_file: 'writetext',
  grep_file_content: 'grep',
  search_file_content: 'grep',
  get_current_time: 'timenow',
};

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
  // 2026-08-27 小欧 三堂会审: 先经CANONICAL归一化长名再路由
  // 2026-08-27 小欧 三堂会审: 据"严禁退化"铁规保留早退 — 专用渲染器要求execution_result.data为对象,
  // 但后端08-18新契约data由data_text(JSON字符串)承载, 纯文本工具解析失败会渲染空(退化), 故优先DefaultRenderer渲染tool_result
  if (step.tool_result && Array.isArray(step.tool_result) && step.tool_result.length) {
    return <DefaultRenderer step={step} />;
  }
  const name = CANONICAL[step.tool_name ?? ''] ?? step.tool_name ?? ''; // 2026-08-27 小欧 三堂会审: 归一化工具名(防undefined索引)
  switch (name) {
    // ===== 文件工具（后端注册名）=====
    case "listdir":
      return <ListDirectoryRenderer step={step} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "readtext":
      return <ReadFileRenderer step={step} />;
    case "writetext":
      return <WriteFileRenderer step={step} />;
    case "delete":
      return <DeleteFileRenderer step={step} />;
    case "move":
      return <MoveFileRenderer step={step} />;
    case "find":
      return <SearchFilesRenderer step={step} />;
    case "grep":
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
