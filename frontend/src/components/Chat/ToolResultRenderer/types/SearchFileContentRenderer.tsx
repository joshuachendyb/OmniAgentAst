/**
 * SearchFileContentRenderer - search_file_content 工具结果渲染器
 * 
 * 从ExecutionStep提取数据并调用SearchFileContentView渲染
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../../utils/sse";
import SearchFileContentView from "../../views/SearchFileContentView";
import { transformSearchFileContentData } from "../../../../utils/searchTransformers";

interface SearchFileContentRendererProps {
  step: ExecutionStep;
}

const SearchFileContentRenderer: React.FC<SearchFileContentRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return null;
  }

  const transformedData = transformSearchFileContentData(data);
  return <SearchFileContentView data={transformedData} />;
};

export default React.memo(SearchFileContentRenderer);
