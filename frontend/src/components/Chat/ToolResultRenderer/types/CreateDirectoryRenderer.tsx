/**
 * CreateDirectoryRenderer - create_directory 工具结果渲染�? * 
 * 从ExecutionStep提取数据并调用CreateDirectoryView渲染
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";

import CreateDirectoryView from "../../views/CreateDirectoryView";
import { BaseRendererProps } from "./BaseRendererProps";

interface CreateDirectoryRendererProps extends BaseRendererProps {}

const CreateDirectoryRenderer: React.FC<CreateDirectoryRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 目录创建数据为空
      </div>
    );
  }

  return <CreateDirectoryView data={data} />;
};

export default React.memo(CreateDirectoryRenderer);