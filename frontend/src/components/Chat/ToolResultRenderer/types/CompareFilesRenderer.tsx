/**
 * CompareFilesRenderer - compare_files 工具结果渲染�? * 
 * 从ExecutionStep提取数据并调用CompareFilesView渲染
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";

import CompareFilesView from "../../views/CompareFilesView";
import { BaseRendererProps } from "./BaseRendererProps";

interface CompareFilesRendererProps extends BaseRendererProps {}

const CompareFilesRenderer: React.FC<CompareFilesRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ⚠️ 文件比较数据为空
      </div>
    );
  }

  return <CompareFilesView data={data} />;
};

export default React.memo(CompareFilesRenderer);