/**
 * SearchFilesRenderer - search_files 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用SearchFilesView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import SearchFilesView from "../../views/SearchFilesView";
import { transformSearchFilesData } from "../../../../utils/searchTransformers";

interface SearchFilesRendererProps {
  step: ExecutionStep;
}

const SearchFilesRenderer: React.FC<SearchFilesRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;

  if (!data) {
    return null;
  }

  const transformedData = transformSearchFilesData(data);
  return <SearchFilesView data={transformedData} />;
};

export default React.memo(SearchFilesRenderer);
