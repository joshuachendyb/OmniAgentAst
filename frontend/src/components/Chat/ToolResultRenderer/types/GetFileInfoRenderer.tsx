/**
 * GetFileInfoRenderer - get_file_info 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用GetFileInfoView渲染
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import GetFileInfoView from "../../views/GetFileInfoView";

interface GetFileInfoRendererProps {
  step: ExecutionStep;
}

const GetFileInfoRenderer: React.FC<GetFileInfoRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 文件信息数据为空
      </div>
    );
  }

  return <GetFileInfoView data={data} />;
};

export default React.memo(GetFileInfoRenderer);