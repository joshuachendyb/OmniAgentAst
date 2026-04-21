/**
 * DefaultRenderer - 默认工具结果渲染器
 * 
 * 当tool_name未知时，显示原始JSON数据
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";

interface DefaultRendererProps {
  step: ExecutionStep;
}

const DefaultRenderer: React.FC<DefaultRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;

  if (!data) {
    return null;
  }

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
};

export default React.memo(DefaultRenderer);
