/**
 * MoveFileRenderer - move_file 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用MoveFileView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import MoveFileView from "../../views/MoveFileView";

interface MoveFileRendererProps {
  step: ExecutionStep;
}

const MoveFileRenderer: React.FC<MoveFileRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;

  if (!data) {
    return null;
  }

  return <MoveFileView data={data} />;
};

export default React.memo(MoveFileRenderer);
