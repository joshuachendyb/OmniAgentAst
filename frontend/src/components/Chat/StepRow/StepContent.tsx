/**
 * StepContent组件 - 步骤内容（根据type渲染不同内容）
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React, { useState } from "react";
import type { ExecutionStep } from "../../../utils/sse";
import ErrorDetail from "../ErrorDetail";
import ToolResultRenderer from "../ToolResultRenderer/index";
import {
  getStepStyle,
  getStepTitleStyle,
  getStepContentStyle,
  getStepBadgeStyle,
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
}

/**
 * 工具信息渲染函数
 */
const renderToolInfo = (toolName: string | undefined, toolParams: Record<string, unknown> | undefined, options?: {
  prefix?: string;
  bgColor?: string;
}) => {
  const prefix = options?.prefix || '';
  const bgColor = options?.bgColor || 'transparent';
  
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
      {/* 2026-04-28 小强修改：tool_params不截断，完全显示 - by 北京老陈 */}
      {toolParams && Object.keys(toolParams).length > 0 && (
        <span style={{ 
          color: '#595959',
          fontSize: 12,
          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
          background: bgColor,
          padding: bgColor !== 'transparent' ? '6px 12px' : '0',
          borderRadius: bgColor !== 'transparent' ? 6 : 0,
          // 北京老陈要求：不截断，完全显示
          maxWidth: 'none',
          overflow: 'visible',
          textOverflow: 'clip',
          whiteSpace: 'pre-wrap',
          display: 'inline-block',
          border: bgColor !== 'transparent' ? '1px solid rgba(0,0,0,0.08)' : 'none',
          wordBreak: 'break-all',
        }}>
          {JSON.stringify(toolParams)}
        </span>
      )}
    </div>
  );
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
}) => {
  const [_showAllData, _setShowAllData] = useState(false);

  const isExpanded = expandedSteps.get(stepIndex) ?? true;
  
  return (
    <div style={{ ...contentStyle, marginTop: 4, marginLeft: 0 }}>
      {step.type === "action_tool" && (
        <>
          {renderToolInfo(step.tool_name, step.tool_params as Record<string, unknown>, { prefix: '🔧 ' })}
          <div style={{ marginTop: 8 }}>
            <ToolResultRenderer step={step} isExpanded={isExpanded} toggleExpand={toggleExpand} stepIndex={stepIndex} />
          </div>
        </>
      )}
      {step.type === "observation" && String((step as ExecutionStep & Record<string, unknown>).observation || '') && (
        <div style={{ 
          ...getStepStyle("observation" as StepType),
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {(step as ExecutionStep & Record<string, unknown>).tool_name && (
            <div style={{ fontSize: "12px", color: "#666", marginBottom: "4px" }}>
              🔧 工具：{(step as ExecutionStep & Record<string, unknown>).tool_name}
              {(step as ExecutionStep & Record<string, unknown>).tool_params && ` ${JSON.stringify((step as ExecutionStep & Record<string, unknown>).tool_params)}`}
            </div>
          )}
          {(step as ExecutionStep & Record<string, unknown>).return_direct && (
            <div style={{ fontSize: "12px", color: "#52c41a", marginBottom: 4 }}>
              🏁 直接返回结果
            </div>
          )}
          <span style={getStepContentStyle("observation" as StepType, "primary")}>
            {String((step as ExecutionStep & Record<string, unknown>).observation || '')}
          </span>
        </div>
      )}
      {step.type === "start" && (
        <div style={getStepStyle("start" as StepType)}>
          <div style={getStepTitleStyle("start" as StepType)}>
            🚀 用户消息：{(step as ExecutionStep & Record<string, unknown>).user_message || "(无)"}
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
          {(step as ExecutionStep & Record<string, unknown>).provider || (step as ExecutionStep & Record<string, unknown>).model || (step as ExecutionStep & Record<string, unknown>).display_name ? (
            <div style={{ 
              marginTop: 4,
              fontSize: FontSize.SMALL,
              display: 'flex',
              flexWrap: 'wrap',
              gap: 12,
            }}>
              {(step as ExecutionStep & Record<string, unknown>).provider && (
                <span>
                  <span style={{ color: Colors.TEXT.TERTIARY, fontWeight: FontWeight.MEDIUM }}>provider：</span>
                  <span style={{ color: Colors.TEXT.PRIMARY, fontWeight: FontWeight.MEDIUM }}>{(step as ExecutionStep & Record<string, unknown>).provider}</span>
                </span>
              )}
              {(step as ExecutionStep & Record<string, unknown>).model && (
                <span>
                  <span style={{ color: Colors.TEXT.TERTIARY, fontWeight: FontWeight.MEDIUM }}>model：</span>
                  <span style={{ color: Colors.TEXT.PRIMARY, fontWeight: FontWeight.MEDIUM }}>{(step as ExecutionStep & Record<string, unknown>).model}</span>
                </span>
              )}
              {(step as ExecutionStep & Record<string, unknown>).display_name && (
                <span>
                  <span style={{ color: Colors.TEXT.TERTIARY, fontWeight: FontWeight.MEDIUM }}>display_name：</span>
                  <span style={{ color: Colors.TEXT.PRIMARY, fontWeight: FontWeight.MEDIUM }}>{(step as ExecutionStep & Record<string, unknown>).display_name}</span>
                </span>
              )}
            </div>
          ) : null}
        </div>
      )}
      {step.type === "thought" && (
        // 2026-04-28 小强修改：第三步实现thought/reasoning样式简化
        <div style={{ 
          ...getStepStyle("thought" as StepType),
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {(step as ExecutionStep & Record<string, unknown>).thought || (step as ExecutionStep & Record<string, unknown>).reasoning ? (
            <div style={{
              marginBottom: 10,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}>
              {/* thought主要内容的简洁样式（第三步修改） */}
              {(step as ExecutionStep & Record<string, unknown>).thought && (
                <div style={{
                  padding: "12px 16px",
                  borderRadius: 10,
                  background: "#fafafa",
                  border: "1px solid #f0f0f0",
                  marginBottom: 8,
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
                    color: '#333',
                    lineHeight: 1.5,
                    fontWeight: 500,
                  }}>
                    {(step as ExecutionStep & Record<string, unknown>).thought}
                  </div>
                </div>
              )}
              {/* reasoning次要信息，左侧竖线标识（第三步修改） */}
              {(step as ExecutionStep & Record<string, unknown>).reasoning && (
                <div style={{
                  marginTop: 8,
                  marginLeft: 0,
                  paddingLeft: 4,
                  borderLeft: "2px solid #d9d9d9",
                  color: "#666",
                  fontSize: 12,
                  lineHeight: 1.5,
                }}>
                  <span style={{ fontWeight: 500, marginRight: 4 }}>🧠 推理:</span>
                  <span style={{ color: '#666' }}>
                    {(step as ExecutionStep & Record<string, unknown>).reasoning}
                  </span>
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
          }}>
            {renderToolInfo((step as ExecutionStep & Record<string, unknown>).tool_name, (step as ExecutionStep & Record<string, unknown>).tool_params as Record<string, unknown>, { 
              prefix: '⬇️ 下一步：', 
              bgColor: 'transparent' 
            })}
          </div>
        </div>
      )}
      {step.type === "final" && (
        <div style={{...getStepStyle("final" as StepType), whiteSpace: "pre-wrap", wordBreak: "break-word"}}>
          {(step as ExecutionStep & Record<string, unknown>).thought && (
            <div style={{fontSize: "12px", color: "#888", marginBottom: "4px"}}>
              思考: {(step as ExecutionStep & Record<string, unknown>).thought}
            </div>
          )}
          <span style={getStepContentStyle("final" as StepType, "primary")}>
            {(step as ExecutionStep & Record<string, unknown>).response || ""}
          </span>
        </div>
      )}
      {step.type === "error" && (
        <ErrorDetail
          errorType={(step as ExecutionStep & Record<string, unknown>).error_type}
          errorMessage={step.error_message || (step as ExecutionStep & Record<string, unknown>).message}
          errorTimestamp={typeof step.timestamp === 'number' ? new Date(step.timestamp).toISOString() : String(step.timestamp)}
          errorDetails={(step as ExecutionStep & Record<string, unknown>).details}
          errorStack={(step as ExecutionStep & Record<string, unknown>).stack}
          errorRetryAfter={(step as ExecutionStep & Record<string, unknown>).retry_after}
          model={(step as ExecutionStep & Record<string, unknown>).model}
          provider={(step as ExecutionStep & Record<string, unknown>).provider}
          errorRecoverable={(step as ExecutionStep & Record<string, unknown>).recoverable}
          errorContext={(step as ExecutionStep & Record<string, unknown>).context}
        />
      )}
      {(step.type === "interrupted" || (step.type === "incident" && (step as ExecutionStep & Record<string, unknown>).incident_value === "interrupted")) && (
        <div style={getStepStyle("interrupted" as StepType)}>
          <span style={getStepContentStyle("interrupted" as StepType, "primary")}>
            {step.content || "客户端断开连接，任务中断"}
          </span>
        </div>
      )}
      {(step.type === "paused" || (step.type === "incident" && (step as ExecutionStep & Record<string, unknown>).incident_value === "paused")) && (
        <div style={getStepStyle("paused" as StepType)}>
          <span style={getStepContentStyle("paused" as StepType, "primary")}>
            {step.content || "任务已暂停，可恢复继续"}
          </span>
        </div>
      )}
      {(step.type === "resumed" || (step.type === "incident" && (step as ExecutionStep & Record<string, unknown>).incident_value === "resumed")) && (
        <div style={getStepStyle("resumed" as StepType)}>
          <span style={getStepContentStyle("resumed" as StepType, "primary")}>
            {step.content || "任务已恢复"}
          </span>
        </div>
      )}
      {(step.type === "retrying" || (step.type === "incident" && (step as ExecutionStep & Record<string, unknown>).incident_value === "retrying")) && (
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
