/**
 * GenerateReportRenderer - generate_report 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用GenerateReportView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import GenerateReportView from "../../views/GenerateReportView";

interface GenerateReportRendererProps {
  step: ExecutionStep;
  isExpanded?: boolean;
  onToggle?: () => void;
}

const GenerateReportRenderer: React.FC<GenerateReportRendererProps> = ({
  step,
  isExpanded = true,
  onToggle,
}) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return null;
  }

  return (
    <GenerateReportView 
      data={data} 
      isExpanded={isExpanded} 
      onToggle={onToggle} 
    />
  );
};

export default React.memo(GenerateReportRenderer);
