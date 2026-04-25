/**
 * BatchRenameRenderer - batch_rename 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用BatchRenameView渲染
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import BatchRenameView from "../../views/BatchRenameView";

interface BatchRenameRendererProps {
  step: ExecutionStep;
}

const BatchRenameRenderer: React.FC<BatchRenameRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 批量重命名数据为空
      </div>
    );
  }

  return <BatchRenameView data={data} />;
};

export default React.memo(BatchRenameRenderer);