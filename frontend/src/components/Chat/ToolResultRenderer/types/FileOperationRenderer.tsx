import React from "react";
import FileOperationView from "../../views/FileOperationView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const FileOperationRenderer: React.FC<Props> = ({ step }) => {
  // 【修复 2026-05-11 小健】execution_result就是data部分
  const data = step.execution_result as Record<string, unknown>;
  const message = (data?.message || "") as string;
  const success = data?.success === true;
  
  return <FileOperationView message={message} success={success} />;
};
export default React.memo(FileOperationRenderer);
