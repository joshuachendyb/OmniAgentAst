/**
 * CompressFilesRenderer - compress_files 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用CompressFilesView渲染
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import CompressFilesView from "../../views/CompressFilesView";

interface CompressFilesRendererProps {
  step: ExecutionStep;
}

const CompressFilesRenderer: React.FC<CompressFilesRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 文件压缩数据为空
      </div>
    );
  }

  return <CompressFilesView data={data} />;
};

export default React.memo(CompressFilesRenderer);