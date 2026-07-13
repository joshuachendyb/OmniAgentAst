/**
 * MoveFileRenderer - move 工具结果渲染器
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空；llm_data.summary 如「移动成功: A -> B」。
 *   成功判定以 llm_data.status.exec_code === "success" 为准。
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from "react";

import MoveFileView from "../../views/MoveFileView";
import { BaseRendererProps } from "./BaseRendererProps";

interface MoveFileRendererProps extends BaseRendererProps {}

const MoveFileRenderer: React.FC<MoveFileRendererProps> = ({ step }) => {
  const execResult = (step.execution_result || {}) as Record<string, unknown>;
  const data = (execResult.data || {}) as Record<string, unknown>;
  const llmData = (execResult.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;

  const success = status.exec_code === "success";
  const summary = (llmData.summary as string) || "";

  if (!data && !llmData) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 数据为空
      </div>
    );
  }

  return <MoveFileView summary={summary} success={success} />;
};

export default React.memo(MoveFileRenderer);
