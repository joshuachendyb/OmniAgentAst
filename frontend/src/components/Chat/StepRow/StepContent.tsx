/**
 * StepContent组件 - 步骤内容（根据type渲染不同内容）
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React, { useCallback, useState, useMemo } from "react";
import type { ExecutionStep } from "../../../utils/sse";
import { STEP_LABEL_MAP, STEP_ICON_MAP } from "../constants/stepConstants";
import ErrorDetail from "../ErrorDetail";
import ListDirectoryView from "../views/ListDirectoryView";
import ReadFileView from "../views/ReadFileView";
import WriteFileView from "../views/WriteFileView";
import DeleteFileView from "../views/DeleteFileView";
import MoveFileView from "../views/MoveFileView";
import SearchFilesView from "../views/SearchFilesView";
import SearchFileContentView from "../views/SearchFileContentView";
import GenerateReportView from "../views/GenerateReportView";
import { transformSearchFilesData, transformSearchFileContentData } from "../../../utils/searchTransformers";
import {
  getStepStyle,
  getStepTitleStyle,
  getStepContentStyle,
  getStepBadgeStyle,
  getTimestampStyle,
  FontSize,
  FontWeight,
  Colors,
  type StepType
} from "../../../utils/stepStyles";

interface StepContentProps {
  step: ExecutionStep;
  stepIndex: number;
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
  contentStyle: React.CSSProperties;
  handleLoadMore: () => void;
  handleLinkMouseEnter: (e: React.MouseEvent<HTMLSpanElement>) => void;
  handleLinkMouseLeave: (e: React.MouseEvent<HTMLSpanElement>) => void;
}

/**
 * 工具信息渲染函数
 */
const renderToolInfo = (toolName: string | undefined, toolParams: Record<string, any> | undefined, options?: {
  prefix?: string;
  bgColor?: string;
}) => {
  const prefix = options?.prefix || '';
  const bgColor = options?.bgColor || 'rgba(0,0,0,0.03)';
  
  if (!toolName && !toolParams) return null;
  
  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      flexWrap: 'wrap', 
      gap: 10,
    }}>
      {toolName && (
        <span style={{ fontWeight: FontWeight.MEDIUM }}>
          {prefix}{toolName}
        </span>
      )}
      {toolParams && Object.keys(toolParams).length > 0 && (
        <span style={{ 
          color: '#595959',
          fontSize: 11,
          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
          background: bgColor,
          padding: '2px 6px',
          borderRadius: 4,
          maxWidth: '60%',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          display: 'inline-block',
        }}>
          {JSON.stringify(toolParams)}
        </span>
      )}
    </div>
  );
};

/**
 * 获取分页数据
 */
const getPageData = (executionResult: any, showAllData: boolean) => {
  const rawData = executionResult as any;
  const allData = rawData?.matches || rawData?.entries || rawData?.results || [];
  const FRONTEND_PAGE_SIZE = 100;
  
  if (showAllData) {
    return { displayData: allData, hasMore: false };
  }
  
  if (allData.length > FRONTEND_PAGE_SIZE) {
    return { displayData: allData.slice(0, FRONTEND_PAGE_SIZE), hasMore: true };
  }
  
  return { displayData: allData, hasMore: false };
};

/**
 * renderToolResult函数 - 根据tool_name渲染工具结果
 */
const renderToolResult = (step: ExecutionStep, isExpanded: boolean = true, toggleExpand?: (index: number) => void, stepIndex?: number) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;
  if (!data) return null;

  const handleToggle = toggleExpand && stepIndex !== undefined ? () => toggleExpand(stepIndex) : undefined;

  switch (step.tool_name) {
    case "list_directory":
      return <ListDirectoryView data={data} toolParams={step.tool_params} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "read_file":
      return <ReadFileView data={data} />;
    case "write_file":
      return <WriteFileView data={data} />;
    case "delete_file":
      return <DeleteFileView data={data} />;
    case "move_file":
      return <MoveFileView data={data} />;
    case "search_files": {
      const transformedSearchFilesData = transformSearchFilesData(data);
      return <SearchFilesView data={transformedSearchFilesData} />;
    }
    case "search_file_content": {
      const transformedSearchFileContentData = transformSearchFileContentData(data);
      return <SearchFileContentView data={transformedSearchFileContentData} />;
    }
    case "generate_report":
      return <GenerateReportView data={data} isExpanded={isExpanded} onToggle={handleToggle} />;
    default:
      return (
        <pre style={{
          background: "#f5f5f5",
          padding: "10px",
          borderRadius: 4,
          fontSize: 12,
          maxHeight: 300,
          overflow: "auto",
        }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
};

/**
 * StepContent组件 - 根据step.type渲染不同内容
 */
const StepContent: React.FC<StepContentProps> = ({
  step,
  stepIndex,
  expandedSteps,
  toggleExpand,
  contentStyle,
  handleLoadMore,
  handleLinkMouseEnter,
  handleLinkMouseLeave,
}) => {
  const [_showAllData, setShowAllData] = useState(false);
  const [_isLoadingMore, _setIsLoadingMore] = useState(false);

  const isExpanded = expandedSteps.get(stepIndex) ?? true;
  const executionResult = step.execution_result;

  const handleInternalLoadMore = useCallback(() => {
    setShowAllData(true);
    handleLoadMore();
  }, [handleLoadMore]);

  const { hasMore } = getPageData(executionResult, _showAllData);

  const effectiveType = step.type === 'incident' ? (step as any).incident_value || 'incident' : step.type;

  return (
    <div style={{ ...contentStyle, marginTop: 4, marginLeft: 0 }}>
      {step.type === "action_tool" && (
        <>
          {renderToolInfo(step.tool_name, step.tool_params as Record<string, any>, { prefix: '🔧 ' })}
          <div style={{ marginTop: 8 }}>
            {renderToolResult(step, isExpanded, toggleExpand, stepIndex)}
          </div>
          {executionResult && step.tool_name !== "list_directory" && hasMore && (
            <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
              <span 
                onClick={handleInternalLoadMore}
                style={{ 
                  cursor: "pointer", 
                  color: "#1890ff",
                  textDecoration: "underline",
                  fontWeight: 500,
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={handleLinkMouseEnter}
                onMouseLeave={handleLinkMouseLeave}
              >
                加载更多
              </span>
            </div>
          )}
          {(step as any).execution_status && (
            <div style={{ marginTop: 6, fontSize: 12 }}>
              <span style={{ 
                color: (step as any).execution_status === "success" ? "#52c41a" : "#ff4d4f",
                fontWeight: 500 
              }}>
                {(step as any).execution_status === "success" ? "✅ 成功" : "❌ 失败"}
              </span>
              {(step as any).execution_time_ms !== undefined && (step as any).execution_time_ms > 0 && (
                <span style={{ color: "#666", marginLeft: 8 }}>
                  | ⏱️ 耗时：{(() => {
                    const ms = (step as any).execution_time_ms;
                    if (!ms || ms <= 0) return "";
                    if (ms < 1000) return `${ms}ms`;
                    return `${(ms / 1000).toFixed(1)}s`;
                  })()}
                </span>
              )}
              {(step as any).action_retry_count !== undefined && (step as any).action_retry_count > 0 && (
                <span style={{ color: "#faad14", marginLeft: 8 }}>
                  | 🔄 重试：{(step as any).action_retry_count}次
                </span>
              )}
              {(step as any).summary && (
                <span style={{ color: "#666", marginLeft: 8 }}>
                  | 📝 {(step as any).summary}
                </span>
              )}
              {(step as any).error_message && (
                <span style={{ color: "#ff4d4f", marginLeft: 8 }}>
                  | ❌ {(step as any).error_message}
                </span>
              )}
            </div>
          )}
        </>
      )}
      {step.type === "observation" && (step as any).observation && (
        <div style={{ 
          ...getStepStyle("observation" as StepType),
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {(step as any).tool_name && (
            <div style={{ fontSize: "12px", color: "#666", marginBottom: "4px" }}>
              🔧 工具：{(step as any).tool_name}
              {(step as any).tool_params && ` ${JSON.stringify((step as any).tool_params)}`}
            </div>
          )}
          {(step as any).return_direct && (
            <div style={{ fontSize: "12px", color: "#52c41a", marginBottom: 4 }}>
              🏁 直接返回结果
            </div>
          )}
          <span style={getStepContentStyle("observation" as StepType, "primary")}>
            {(step as any).observation}
          </span>
        </div>
      )}
      {step.type === "start" && (
        <div style={getStepStyle("start" as StepType)}>
          <div style={getStepTitleStyle("start" as StepType)}>
            🚀 用户消息：{(step as any).user_message || "(无)"}
          </div>
          <div style={{ 
            ...getStepContentStyle("start" as StepType, "secondary"),
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 8,
          }}>
            <span style={{ marginRight: 16 }}>
              <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>任务ID：</span>
              <span style={getStepBadgeStyle("start")}>
                {step.task_id || "无"}
              </span>
            </span>
            {step.security_check && (
              <span style={{ marginRight: 16 }}>
                <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>安全：</span>
                <span style={{ 
                  color: step.security_check.is_safe ? Colors.SUCCESS : Colors.ERROR,
                  fontWeight: FontWeight.BOLD,
                  backgroundColor: step.security_check.is_safe ? "rgba(82,196,26,0.1)" : "rgba(255,77,79,0.1)",
                  padding: "2px 8px",
                  borderRadius: 4,
                  fontSize: FontSize.SMALL,
                }}>
                  {step.security_check.is_safe ? "✅ 通过" : "⚠️ 拦截"}
                </span>
                {!step.security_check.is_safe && step.security_check.risk && (
                  <span style={{ color: Colors.ERROR, marginLeft: 6, fontSize: FontSize.TERTIARY }}>
                    ({step.security_check.risk})
                  </span>
                )}
              </span>
            )}
            <span style={{ flex: 1 }} />
          </div>
          {(step as any).provider || (step as any).model || (step as any).display_name ? (
            <div style={{ 
              marginTop: 4,
              padding: '6px 10px',
              borderRadius: 6,
              background: 'rgba(24,144,255,0.06)',
              border: '1px solid rgba(24,144,255,0.15)',
              fontSize: FontSize.SMALL,
              display: 'flex',
              flexWrap: 'wrap',
              gap: 12,
            }}>
              {(step as any).provider && (
                <span>
                  <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>provider：</span>
                  <span style={{ color: '#1890ff', fontWeight: FontWeight.MEDIUM }}>{(step as any).provider}</span>
                </span>
              )}
              {(step as any).model && (
                <span>
                  <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>model：</span>
                  <span style={{ color: '#1890ff', fontWeight: FontWeight.MEDIUM }}>{(step as any).model}</span>
                </span>
              )}
              {(step as any).display_name && (
                <span>
                  <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>display_name：</span>
                  <span style={{ color: '#1890ff', fontWeight: FontWeight.MEDIUM }}>{(step as any).display_name}</span>
                </span>
              )}
            </div>
          ) : null}
        </div>
      )}
      {step.type === "thought" && (
        <div style={{ 
          ...getStepStyle("thought" as StepType),
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {(step as any).thought || (step as any).reasoning ? (
            <div style={{
              marginBottom: 10,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}>
              {(step as any).thought && (
                <div style={{
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, rgba(250,173,20,0.12) 0%, rgba(255,165,0,0.08) 100%)',
                  border: '1px solid rgba(255,170,0,0.25)',
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    marginBottom: 6,
                  }}>
                    <span style={{ fontSize: 14 }}>💭</span>
                    <span style={{ 
                      fontSize: 12, 
                      fontWeight: 600,
                      color: '#d97706',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>思考</span>
                  </div>
                  <div style={{
                    fontSize: 13,
                    color: '#92400e',
                    lineHeight: 1.5,
                  }}>
                    {(step as any).thought}
                  </div>
                </div>
              )}
              {(step as any).reasoning && (
                <div style={{
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, rgba(139,92,246,0.1) 0%, rgba(167,139,250,0.06) 100%)',
                  border: '1px solid rgba(167,139,250,0.2)',
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    marginBottom: 6,
                  }}>
                    <span style={{ fontSize: 14 }}>🧠</span>
                    <span style={{ 
                      fontSize: 12, 
                      fontWeight: 600,
                      color: '#7c3aed',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>推理</span>
                  </div>
                  <div style={{
                    fontSize: 13,
                    color: '#6d28d9',
                    lineHeight: 1.5,
                  }}>
                    {(step as any).reasoning}
                  </div>
                </div>
              )}
            </div>
          ) : null}
          <div>
            <span style={getStepContentStyle("thought" as StepType, "primary")}>
              {step.content || ""}
            </span>
          </div>
          <div style={{
            marginTop: 6,
            padding: '8px 12px',
            borderRadius: 6,
            background: 'linear-gradient(135deg, rgba(250,173,20,0.08) 0%, rgba(212,136,6,0.08) 100%)',
            border: '1px solid rgba(255,213,145,0.3)',
          }}>
            {renderToolInfo((step as any).tool_name, (step as any).tool_params as Record<string, any>, { 
              prefix: '⬇️ 下一步：', 
              bgColor: 'rgba(255,170,0,0.1)' 
            })}
          </div>
        </div>
      )}
      {step.type === "final" && (
        <div style={getStepStyle("final" as StepType)}>
          {(step as any).thought && (
            <div style={{fontSize: "12px", color: "#888", marginBottom: "4px"}}>
              思考: {(step as any).thought}
            </div>
          )}
          <span style={getStepContentStyle("final" as StepType, "primary")}>
            {(step as any).response || ""}
          </span>
        </div>
      )}
      {step.type === "error" && (
        <ErrorDetail
          errorType={(step as any).error_type}
          errorMessage={step.error_message || (step as any).message}
          errorTimestamp={typeof step.timestamp === 'number' ? new Date(step.timestamp).toISOString() : String(step.timestamp)}
          errorDetails={(step as any).details}
          errorStack={(step as any).stack}
          errorRetryAfter={(step as any).retry_after}
          model={(step as any).model}
          provider={(step as any).provider}
          errorRecoverable={(step as any).recoverable}
          errorContext={(step as any).context}
        />
      )}
      {(step.type === "interrupted" || (step.type === "incident" && (step as any).incident_value === "interrupted")) && (
        <div style={getStepStyle("interrupted" as StepType)}>
          <span style={getStepContentStyle("interrupted" as StepType, "primary")}>
            {step.content || "客户端断开连接，任务中断"}
          </span>
        </div>
      )}
      {(step.type === "paused" || (step.type === "incident" && (step as any).incident_value === "paused")) && (
        <div style={getStepStyle("paused" as StepType)}>
          <span style={getStepContentStyle("paused" as StepType, "primary")}>
            {step.content || "任务已暂停，可恢复继续"}
          </span>
        </div>
      )}
      {(step.type === "resumed" || (step.type === "incident" && (step as any).incident_value === "resumed")) && (
        <div style={getStepStyle("resumed" as StepType)}>
          <span style={getStepContentStyle("resumed" as StepType, "primary")}>
            {step.content || "任务已恢复"}
          </span>
        </div>
      )}
      {(step.type === "retrying" || (step.type === "incident" && (step as any).incident_value === "retrying")) && (
        <div style={getStepStyle("retrying" as StepType)}>
          <span style={getStepContentStyle("retrying" as StepType, "primary")}>
            {step.content || "正在重试..."}
          </span>
        </div>
      )}
    </div>
  );
};

export default React.memo(StepContent);
