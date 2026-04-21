/**
 * Message Exporter - 消息导出工具
 * 
 * 导出消息为JSON或TXT格式
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import { message as antMessage } from "antd";
import type { ChatMessage } from "../services/api";
import type { ExecutionStep } from "./sse";
import { formatTimestamp } from "./timestamp";

/**
 * 导出数据结构
 */
export interface ExportData {
  sessionId?: string;
  sessionTitle?: string;
  timestamp: string;
  messageId: string;
  role: string;
  content: string;
  executionSteps?: Record<string, any>[];
  error?: Record<string, any>;
  incidentSteps?: Record<string, any>[];
}

/**
 * 导出选项
 */
export interface ExportOptions {
  sessionId?: string | null;
  sessionTitle?: string | null;
}

/**
 * 导出消息内容
 * @param message 消息对象
 * @param options 导出选项
 */
export const exportMessage = async (
  message: ChatMessage & {
    id: string;
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    model?: string;
    provider?: string;
    isStreaming?: boolean;
    isError?: boolean;
    display_name?: string;
    is_reasoning?: boolean;
    task_id?: string;
    errorType?: string;
    errorMessage?: string;
    errorRetryAfter?: number;
    errorTimestamp?: string;
    errorRecoverable?: boolean;
    errorContext?: Record<string, any>;
  },
  options: ExportOptions = {}
): Promise<void> => {
  const { sessionId, sessionTitle } = options;
  const { formatTimestamp: fmtTs } = { formatTimestamp };

  const hasSteps = message.executionSteps && message.executionSteps.length > 0;
  const isError = message.isError;

  let blob: Blob;
  let filename: string;

  const exportData: ExportData = {
    sessionId: sessionId || undefined,
    sessionTitle: sessionTitle || undefined,
    timestamp: formatTimestamp(message.timestamp instanceof Date ? message.timestamp.getTime() : message.timestamp),
    messageId: message.id,
    role: message.role,
    content: message.content,
  };

  const hasIncident = hasSteps && message.executionSteps?.some(
    (step) => step.type === 'incident'
  );

  if (hasIncident) {
    exportData.incidentSteps = message.executionSteps?.filter(
      (step) => step.type === 'incident'
    ).map(step => ({
      type: (step as any).incident_value || 'incident',
      incident_value: (step as any).incident_value,
      message: step.content || (step as any).message,
      timestamp: formatTimestamp((step as any).timestamp),
      wait_time: (step as any).wait_time,
    }));
  }

  if (isError) {
    exportData.error = {
      type: "error",
      error_type: message.errorType,
      error_message: message.errorMessage,
      retry_after: message.errorRetryAfter,
      timestamp: formatTimestamp(message.errorTimestamp),
      model: message.model,
      provider: message.provider,
      recoverable: message.errorRecoverable,
      context: message.errorContext,
    };
    exportData.executionSteps = message.executionSteps?.map(step => ({
      ...step,
      timestamp: formatTimestamp(step.timestamp),
    }));
    filename = `error_${message.id}_${new Date().toISOString().replace(/[/:]/g, "-")}.json`;
  } else if (hasSteps) {
    exportData.executionSteps = message.executionSteps?.map(step => {
      const baseExport: Record<string, any> = {
        type: step.type,
        content: step.content,
        timestamp: formatTimestamp(step.timestamp),
      };

      switch (step.type) {
        case 'thought':
          return {
            ...baseExport,
            step: step.step,
            thought: step.thought || "",
            reasoning: step.reasoning || "",
            tool_name: step.tool_name,
            tool_params: step.tool_params
          };
        case 'action_tool':
          return {
            ...baseExport,
            step: step.step,
            tool_name: step.tool_name,
            tool_params: step.tool_params,
            execution_status: step.execution_status,
            summary: step.summary,
            execution_result: step.execution_result || null,
            error_message: step.error_message || "",
            execution_time_ms: step.execution_time_ms || 0,
            action_retry_count: step.action_retry_count
          };
        case 'observation':
          return {
            type: step.type,
            step: step.step,
            timestamp: formatTimestamp(step.timestamp),
            tool_name: step.tool_name,
            tool_params: step.tool_params,
            observation: step.observation || step.content,
            return_direct: (step as any).return_direct
          };
        case 'chunk':
          return { ...baseExport, step: step.step, is_reasoning: step.is_reasoning };
        case 'final':
          return {
            ...baseExport,
            step: step.step,
            timestamp: formatTimestamp(step.timestamp),
            display_name: step.display_name,
            model: step.model,
            provider: step.provider,
            response: (step as any).response,
            thought: step.thought,
            is_finished: (step as any).is_finished,
            is_streaming: (step as any).is_streaming,
            is_reasoning: (step as any).is_reasoning
          };
        case 'error':
          return {
            ...baseExport,
            step: step.step,
            timestamp: formatTimestamp(step.timestamp),
            error_type: (step as any).error_type,
            error_message: (step as any).error_message || "",
            details: (step as any).details,
            stack: (step as any).stack,
            recoverable: (step as any).recoverable,
            retry_after: (step as any).retry_after,
            model: (step as any).model,
            provider: (step as any).provider,
            context: (step as any).context
          };
        case 'interrupted':
        case 'paused':
        case 'resumed':
        case 'retrying':
          return {
            ...baseExport,
            step: step.step,
            incident_value: (step as any).incident_value || step.type,
            wait_time: (step as any).wait_time
          };
        case 'incident':
          return {
            ...baseExport,
            step: step.step,
            type: (step as any).incident_value || 'incident',
            incident_value: (step as any).incident_value,
            message: step.content || (step as any).message,
            wait_time: (step as any).wait_time
          };
        case 'start':
          return {
            ...baseExport,
            task_id: step.task_id,
            step: step.step,
            security_check: step.security_check,
            user_message: step.user_message,
            display_name: step.display_name,
            model: step.model,
            provider: step.provider
          };
        default:
          return baseExport;
      }
    });
    filename = `execution_steps_${new Date().toLocaleString("zh-CN").replace(/[/:]/g, "-").replace(/ /g, "T")}.json`;
  } else {
    const content = message.content || "";
    blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    filename = `message_${message.id}_${new Date().toLocaleString("zh-CN").replace(/[/:]/g, "-")}.txt`;

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    antMessage.success("导出成功");
    return;
  }

  const jsonStr = JSON.stringify(exportData, null, 2);
  blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  antMessage.success("导出成功");
};
