/**
 * ReadFileRenderer - read_file 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用ReadFileView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import ReadFileView from "../../views/ReadFileView";

interface ReadFileRendererProps {
  step: ExecutionStep;
}

const ReadFileRenderer: React.FC<ReadFileRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;

  if (!data) {
    return null;
  }

  return <ReadFileView data={data} />;
};

export default React.memo(ReadFileRenderer);
