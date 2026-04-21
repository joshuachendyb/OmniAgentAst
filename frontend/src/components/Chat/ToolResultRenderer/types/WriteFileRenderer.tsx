/**
 * WriteFileRenderer - write_file 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用WriteFileView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import WriteFileView from "../../views/WriteFileView";

interface WriteFileRendererProps {
  step: ExecutionStep;
}

const WriteFileRenderer: React.FC<WriteFileRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;

  if (!data) {
    return null;
  }

  return <WriteFileView data={data} />;
};

export default React.memo(WriteFileRenderer);
