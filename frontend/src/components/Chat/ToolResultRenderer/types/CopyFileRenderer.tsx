/**
 * CopyFileRenderer - copy_file 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用CopyFileView渲染
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import CopyFileView from "../../views/CopyFileView";

interface CopyFileRendererProps {
  step: ExecutionStep;
}

const CopyFileRenderer: React.FC<CopyFileRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 复制操作数据为空
      </div>
    );
  }

  return <CopyFileView data={data} />;
};

export default React.memo(CopyFileRenderer);