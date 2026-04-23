/**
 * ListDirectoryRenderer - list_directory 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用ListDirectoryView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import ListDirectoryView from "../../views/ListDirectoryView";

interface ListDirectoryRendererProps {
  step: ExecutionStep;
  isExpanded?: boolean;
  onToggle?: () => void;
}

const ListDirectoryRenderer: React.FC<ListDirectoryRendererProps> = ({
  step,
  isExpanded = true,
  onToggle,
}) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;
  const listData = data as { entries: Array<{ name: string; path: string; type: "directory" | "file"; size: number | null }>; total?: number; has_more?: boolean; directory?: string };

  if (!data) {
    return null;
  }

return (
    <ListDirectoryView 
      data={listData} 
      toolParams={step.tool_params as Record<string, unknown>}
      isExpanded={isExpanded} 
      onToggle={onToggle} 
    />
  );
};

export default React.memo(ListDirectoryRenderer);
