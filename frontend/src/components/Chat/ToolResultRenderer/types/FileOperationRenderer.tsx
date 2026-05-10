import React from "react";
import FileOperationView from "../../views/FileOperationView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const FileOperationRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result as Record<string, unknown>;
  const data = (r?.data || {}) as Record<string, unknown>;
  const message = (r?.message || data?.message || "") as string;
  const code = (r?.code || "") as string;
  const success = code === "SUCCESS" || code === "OK" || !!r?.data;
  return <FileOperationView message={message} success={success} />;
};
export default React.memo(FileOperationRenderer);
