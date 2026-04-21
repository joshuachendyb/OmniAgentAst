/**
 * MessageItem组件 - 单条消息展示
 *
 * 功能：展示用户/AI/系统消息，支持头像、时间戳、复制功能
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState, useMemo, useCallback, memo } from "react";
import {
  Avatar,
  Tooltip,
  Button,
  message as antMessage,
} from "antd";
import {
  UserOutlined,
  RobotOutlined,
  InfoCircleOutlined,
  CopyOutlined,
  CheckOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import type { ChatMessage } from "../../services/api";
import type { ExecutionStep } from "../../utils/sse";
import { formatTimestamp } from "../../utils/timestamp";
import { formatTime, formatRelativeTime } from "../../utils/timeFormatters";
import { STEP_LABEL_MAP, STEP_ICON_MAP } from "./constants/stepConstants";
import { DynamicStatusDisplay } from "../../utils/dynamicStatus";
import { } from "../../utils/markdown";
import ErrorDetail from "./ErrorDetail";
import { 
  getStepStyle, 
  getStepTitleStyle,
  getStepContentStyle,
  getStepBadgeStyle,
  getStepLabelStyle,
  getTimestampStyle,
  FontSize,
  FontWeight,
  Colors,
  type StepType 
} from "../../utils/stepStyles";

// 【小强 2026-04-12】Phase 2 P1级优化 - 导入自定义比较函数
import { messageItemCompare } from '../../hooks/useMessageItemProps';

// 【2026-04-21 优化3.2.1】从新拆分的StepRow目录导入
import StepRow from "./StepRow/index";

// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装组件，减少不必要的重渲染
// MessageItemProps 类型已移至 useMessageItemProps.ts 中导出，供外部使用
export interface MessageItemProps {
  message: ChatMessage & {
    id: string;
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    model?: string;
    provider?: string; // 提供商
    isStreaming?: boolean;
    isError?: boolean;
    display_name?: string; // 前端小新代修改：显示名称
    is_reasoning?: boolean; // 【小查修复】是否为思考过程（统一使用 snake_case）
    task_id?: string; // 【小新重构2026-03-09】任务ID，用于分页请求
    // 【小沈修改2026-04-16】error相关字段：删除details/stack/retryable，后端已删除
    errorType?: string;      // error_type
    // 【小沈修改2026-04-15】删除errorCode，统一使用errorMessage
    errorMessage?: string;  // error_message - 错误消息内容 【小沈修改2026-04-15】message → error_message
    errorRetryAfter?: number; // retry_after
    errorTimestamp?: string;  // timestamp
    // 【小沈添加2026-04-15】新增recoverable和context字段
    errorRecoverable?: boolean;
    errorContext?: {
      step?: number;
      model?: string;
      provider?: string;
      thought_content?: string;
    };
  };
  showExecution?: boolean;
  sessionId?: string | null;  // 【小强添加 2026-03-23】会话ID，用于导出
  sessionTitle?: string | null;  // 【小强添加 2026-03-23】会话标题，用于导出
}

/**
 * 消息项组件
 *
 * 设计要点：
 * - 用户消息：蓝色渐变，右侧对齐
 * - AI消息：白色卡片，左侧对齐，绿色边框
 * - 系统消息：浅黄色背景，居中
 * - 悬停显示复制按钮
 *
 * @param message - 消息对象
 * @param showExecution - 是否显示执行过程
 */
/* eslint-disable react/prop-types */
// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装组件，减少不必要的重渲染
// MessageItemProps 在 useMessageItemProps.ts 中导出使用
const MessageItem = memo(({
  message,
  showExecution: _showExecution = false,
  sessionId,
  sessionTitle,
}) => {
  const [copied, setCopied] = useState(false);
  // 【小强修复 2026-03-23】使用Map存储每个步骤的展开状态，支持多步骤独立折叠
  const [expandedSteps, setExpandedSteps] = useState<Map<number, boolean>>(new Map([[0, true]]));

  // 【小强修复 2026-03-23】切换展开状态
  const toggleExpand = (index: number) => {
    setExpandedSteps(prev => {
      const newMap = new Map(prev);
      newMap.set(index, !newMap.get(index));
      return newMap;
    });
  };

  /**
   * 复制消息内容
   */
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      antMessage.success("已复制到剪贴板");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      antMessage.error("复制失败");
    }
  };

  /**
   * 导出消息内容
   * - 有执行步骤：导出JSON格式
   * - 有执行步骤：导出JSON格式（包含所有8种type的完整字段）
   * - 是错误消息：导出JSON格式（包含完整error信息）
   * - 是incident消息：导出JSON格式（包含完整incident信息）
   * 
   * 【重要】8种type说明：
   * - 内容步骤：start（开始）、chunk（AI回复内容片段）、final（最终回答）
   *   【chunk是AI流式输出的内容片段，不是执行步骤，显示在AI回复区域，不在步骤列表】
   * - 执行步骤：thought（思考）、action_tool（工具调用）、observation（工具结果）
   * - 异常步骤：error（错误）、incident（中断）
   */
  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    console.log("🔍 [handleExport] 开始导出, message.id=", message.id);
    try {
      const hasSteps = message.executionSteps && message.executionSteps.length > 0;
      const isError = message.isError;
      console.log("🔍 [handleExport] hasSteps=", hasSteps, "isError=", isError, "executionSteps数量=", message.executionSteps?.length);
      
      let blob: Blob;
      let filename: string;
       
      // 统一的导出数据结构
      const exportData: Record<string, any> = {
        sessionId: sessionId || undefined,  // 【小强添加 2026-03-23】会话ID
        sessionTitle: sessionTitle || undefined,  // 【小强添加 2026-03-23】会话标题
        timestamp: formatTimestamp(message.timestamp instanceof Date ? message.timestamp.getTime() : message.timestamp),
        messageId: message.id,
        role: message.role,
        content: message.content,
      };
      
      // 检查是否包含incident类型的步骤（后端type固定为'incident'，通过incident_value区分具体类型）
      const hasIncident = hasSteps && message.executionSteps?.some(
        (step) => step.type === 'incident'
      );
      
      if (hasIncident) {
        // 【小沈修复2026-03-28】后端type固定为'incident'，通过incident_value区分具体类型
        exportData.incidentSteps = message.executionSteps?.filter(
          (step) => step.type === 'incident'
        ).map(step => ({
          type: (step as any).incident_value || 'incident',  // 使用incident_value作为type
          incident_value: (step as any).incident_value,
          message: step.content || (step as any).message,
          timestamp: formatTimestamp((step as any).timestamp),
          wait_time: (step as any).wait_time,
        }));
      }
       
      if (isError) {
        // 错误消息：导出JSON格式（使用API文档字段名）
        // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除
        exportData.error = {
          type: "error",
          error_type: message.errorType,
          error_message: message.errorMessage,  // 【小沈修改2026-04-15】message → error_message
          retry_after: message.errorRetryAfter,
          timestamp: formatTimestamp(message.errorTimestamp),
          model: message.model,
          provider: message.provider,
          // 【小沈添加2026-04-15】新增recoverable和context
          recoverable: message.errorRecoverable,
          context: message.errorContext,
        };
        // 【小强修复 2026-03-17】executionSteps 也要转换 timestamp
        exportData.executionSteps = message.executionSteps?.map(step => ({
          ...step,
          timestamp: formatTimestamp(step.timestamp),
        }));
        filename = `error_${message.id}_${new Date().toISOString().replace(/[/:]/g, "-")}.json`;
      } else if (hasSteps) {
        // 有执行步骤：导出JSON格式（包含所有8种type的完整字段）
        // 8种type: start, thought, action_tool, observation, chunk, final, error, incident
        exportData.executionSteps = message.executionSteps?.map(step => {
          const baseExport: Record<string, any> = {
            type: step.type,
            content: step.content,
            timestamp: formatTimestamp(step.timestamp),  // 转换为可读格式
          };
          
            // 根据不同type添加对应字段
          switch (step.type) {
            case 'thought':
              // 【小强修复 2026-04-14】添加thought和reasoning字段导出
              return { 
                ...baseExport, 
                step: step.step, 
                thought: step.thought || "",     // LLM思考过程
                reasoning: step.reasoning || "", // LLM推理过程
                tool_name: step.tool_name, 
                tool_params: step.tool_params 
              };
            case 'action_tool':
              // 【小强修改2026-04-15】raw_data → execution_result
              return { ...baseExport, step: step.step, tool_name: step.tool_name, tool_params: step.tool_params, execution_status: step.execution_status, summary: step.summary, execution_result: step.execution_result || null, error_message: step.error_message || "", execution_time_ms: step.execution_time_ms || 0, action_retry_count: step.action_retry_count };
            case 'observation':
              // 【修复 2026-04-16】移除冗余的content字段，只保留observation字段
              // 后端发送的是observation字段，前端content是兼容旧代码
              return { 
                type: step.type,
                step: step.step, 
                timestamp: formatTimestamp(step.timestamp),
                tool_name: step.tool_name,
                tool_params: step.tool_params,
                observation: step.observation || step.content,  // 使用observation字段
                return_direct: (step as any).return_direct
              };
            case 'chunk':
              return { ...baseExport, step: step.step, is_reasoning: step.is_reasoning };
            case 'final':
              // 【小沈修改2026-04-16】添加response/thought/is_finished/is_streaming/is_reasoning
              return { 
                ...baseExport, 
                step: step.step,
                timestamp: formatTimestamp(step.timestamp),
                display_name: step.display_name,
                model: step.model,
                provider: step.provider,
                response: step.response,
                thought: step.thought,
                is_finished: (step as any).is_finished,
                is_streaming: (step as any).is_streaming,
                is_reasoning: (step as any).is_reasoning
              };
            case 'error':
              // 【小沈修改2026-04-16】导出所有后端字段
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
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, step: step.step, incident_value: (step as any).incident_value || step.type, wait_time: (step as any).wait_time };
            case 'incident':
              // 【小沈修复 2026-03-28】后端type固定为'incident'，通过incident_value区分具体类型
              return { 
                ...baseExport, 
                step: step.step, 
                type: (step as any).incident_value || 'incident',  // 导出时还原为具体类型
                incident_value: (step as any).incident_value,
                message: step.content || (step as any).message,
                wait_time: (step as any).wait_time 
              };
            case 'start':
              // 【小强修复 2026-03-18】添加 step 字段
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
        // 无执行步骤：导出TXT格式
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
      
      // JSON格式导出
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
    } catch (err) {
      console.error("🔍 [handleExport] 导出失败, error=", err);
      antMessage.error("导出失败");
    }
  };

  /**
   * 获取角色图标
   */
  const getAvatar = () => {
    switch (message.role) {
      case "user":
        return (
          <Avatar
            size={32}
            icon={<UserOutlined />}
            style={{
              background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
            }}
          />
        );
      case "assistant":
        return (
          <Avatar
            size={32}
            icon={<RobotOutlined />}
            style={{
              background: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
            }}
          />
        );
      case "system":
        return (
          <Avatar
            size={32}
            icon={<InfoCircleOutlined />}
            style={{ background: "#faad14" }}
          />
        );
      default:
        return null;
    }
  };

  /**
   * 获取角色名称
    */
  const getRoleName = () => {
    switch (message.role) {
      case "user":
        return "我";
      case "assistant": {
        // ✅ 老杨 UX 建议：占位消息显示 loading 状态
        // 前端小新代修改：只要 isStreaming 为 true，就显示加载状态，并且显示 display_name
        if (message.isStreaming) {
          // 前端小新代修改：加载状态也显示 display_name（如果存在）
          // 如果 display_name 为空，尝试使用 model 构建
          let display_nameToShow = message.display_name;
          if (!display_nameToShow && message.model) {
            display_nameToShow = message.model;
          }
          
          const result = display_nameToShow
            ? `🤔 AI 助手【${display_nameToShow}】【加载中...】`
            : `🤔 AI 助手【加载中...】`;
          return result;
        }


        // 前端小新代修改 VIS-E02: 错误消息显示错误标识
        if (message.isError) {
          // ✅ 老杨 UX 建议：添加错误图标（⚠️）
          return message.display_name
            ? `⚠️ AI 助手【${message.display_name}】【错误】`
            : `⚠️ AI 助手【错误】`;
        }
        // 直接使用后端返回的 display_name，用【】包住显示
        return message.display_name
          ? `AI 助手【${message.display_name}】`
          : "AI 助手";
      }
      case "system":
        return "系统";
      default:
        return "";
    }
  };

  /**
   * 获取消息样式 - 前端小新代修改 VIS-C01: 圆角优化，VIS-C02: padding 优化，VIS-C03: 阴影优化，VIS-E01: 错误消息样式，UX-C04: 留白优化（用户建议 50%）
   */
  const getMessageStyle = () => {
    const baseStyle: React.CSSProperties = {
      maxWidth: "100%",
      minWidth: "60px",
      width: "auto",
      // 【小查修复2026-03-13】拆分为单独属性，避免与paddingRight冲突
      paddingTop: 8,
      paddingBottom: 8,
      paddingLeft: 10,
      paddingRight: 10,
      borderRadius: "16px",
      position: "relative",
      transition: "all 0.3s ease",
      whiteSpace: "pre-wrap",
      wordBreak: "normal",
      overflowWrap: "break-word",
    };

    // 前端小新代修改 VIS-E01: 错误消息样式
    if (message.role === "assistant" && message.isError) {
      return {
        ...baseStyle,
        background: "#fff1f0",
        border: "1px solid #ffa39e",
        color: "#cf1322",
        boxShadow: "0 4px 12px rgba(255, 77, 79, 0.15)",
      };
    }

    switch (message.role) {
      case "user":
        return {
          ...baseStyle,
          // 【小强优化2026-04-14】轻淡蓝色渐变方案B，更柔和
          background: "linear-gradient(135deg, #f0f5ff 0%, #adc6ff 100%)",
          color: "#262626",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          paddingRight: 30,
          border: "1px solid #d6e4ff",
        };
      case "assistant":
        return {
          ...baseStyle,
          background: "#fff",
          border: "1px solid #b7eb8f",
          color: "#262626",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          paddingRight: 30, // 为右侧按钮留出空间
        };
      case "system":
        return {
          ...baseStyle,
          background: "#fffbe6",
          border: "1px solid #ffe58f",
          color: "#ad6800",
          maxWidth: "90%",
          textAlign: "center" as const,
          whiteSpace: "nowrap" as const, // ✅ 小新修复 2026-03-01 14:38:19：系统消息不折行，覆盖 baseStyle 的 pre-wrap
        };
      default:
        return baseStyle;
    }
  };

  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: isSystem
          ? "center"
          : isUser
          ? "flex-end"
          : "flex-start",
        marginBottom: 12,
        gap: 10,
        width: "100%",
      }}
    >
      {/* 左侧头像（仅AI消息） */}
      {!isUser && !isSystem && (
        <div style={{ flexShrink: 0, marginTop: 6 }}>
          {getAvatar()}
        </div>
      )}

      {/* 消息内容区 - 简化结构 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: isUser ? "flex-end" : "flex-start",
          maxWidth: "calc(100% - 50px)",
        }}
      >
        {/* 角色名称和时间戳区域 */}
        {!isSystem && (
          <div
            style={{
              marginBottom: 4,
              fontSize: 12,
              color: isUser ? "#1890ff" : "#52c41a",
              fontWeight: 500,
              opacity: 0.85,
              whiteSpace: "nowrap",
              display: "flex",
              alignItems: "center",
              gap: isUser ? "0" : "8px",
              flexDirection: isUser ? "row-reverse" : "row",
            }}
          >
            <span style={{ whiteSpace: "nowrap" }}>
              {getRoleName()}
            </span>
            {/* 时间戳移到角色名称同一行 */}
              <span
              style={{
                fontSize: 11,
                color: "#999999",
                whiteSpace: "nowrap",
              }}
            >
              <Tooltip title={formatTime(message.timestamp)}>
                <span>{formatRelativeTime(message.timestamp)}</span>
              </Tooltip>
            </span>
          </div>
        )}

        {/* 消息内容 - 优化后的结构 */}
        <div style={{ ...getMessageStyle(), position: "relative" }}>
          {/* 复制按钮（悬停显示）- 透明背景，小巧精致 */}
          <Tooltip title={copied ? "已复制" : "复制"}>
            <Button
              className="copy-button"
              type="text"
              size="small"
              icon={
                copied ? (
                  <CheckOutlined style={{ color: "#52c41a" }} />
                ) : (
                  <CopyOutlined style={{ color: isUser ? "rgba(255,255,255,0.9)" : "#595959" }} />
                )
              }
              onClick={handleCopy}
              style={{
                position: "absolute",
                top: 4,
                right: 6,
                opacity: 0,
                transition: "opacity 0.2s ease",
                background: "transparent",
                border: "none",
                boxShadow: "none",
                padding: "0 4px",
                minHeight: "auto",
                height: "20px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            />
          </Tooltip>

          {/* 导出按钮 */}
          <Tooltip title="导出">
            <Button
              className="copy-button"
              type="text"
              size="small"
              icon={<DownloadOutlined style={{ color: isUser ? "rgba(255,255,255,0.9)" : "#595959" }} />}
              onClick={handleExport}
              style={{
                position: "absolute",
                top: 4,
                right: 30,
                opacity: 0,
                transition: "opacity 0.2s ease",
                background: "transparent",
                border: "none",
                boxShadow: "none",
                padding: "0 4px",
                minHeight: "auto",
                height: "20px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            />
          </Tooltip>

          <>
          {/* 【小强简化2026-03-18】按step顺序显示 - 用StepRow渲染 */}
          {/* 【重要】过滤逻辑：
           * - chunk：永远不在步骤列表显示（是AI回复内容，在AI回复区域显示）
           * - final：普通对话模式（有chunk）时不显示，ReAct模式时显示
           */}
           {(() => {
               const allSteps = message.executionSteps || [];
               // 【小强修复 2026-04-03】从 start 步骤获取 task_id（SSE 流式时保存在 executionSteps 中）
               const taskId = allSteps.find(s => s.type === 'start')?.task_id;
               // 判断是否是普通对话模式（有 chunk）
               const hasChunk = allSteps.some(step => step.type === 'chunk');
              // 过滤：普通对话模式下过滤 chunk 和 final
              const filteredSteps = allSteps.filter(step => {
                if (step.type === 'chunk') return false;
                if (step.type === 'final' && hasChunk) return false;
                return true;
              });
              const sortedSteps = [...filteredSteps].sort((a, b) => {
                if (a.step && b.step) return a.step - b.step;
                return 0;
              });
              return sortedSteps.map((step, index) => (
                <StepRow key={`step-${index}`} step={step} taskId={taskId} stepIndex={index} expandedSteps={expandedSteps} toggleExpand={toggleExpand} />
              ));
            })()}
              
              {/* 【小新修复】在推理过程中显示"💭 思考中:"标签 */}
            {message.is_reasoning && (
              <span style={{ color: '#888', fontSize: '0.85em', marginRight: 4, fontWeight: 500 }}>
                💭 思考中:
              </span>
            )}

            {/* 【小查修复】4. AI回复chunk - 逐个渲染 */}
            {/* 【小新修复 2026-03-14】is_reasoning切换时自动添加换行 */}
            {/* 
             * 【重要】chunk 显示逻辑分两种情况：
             * 1. SSE实时模式（isStreaming=true）：逐个渲染chunk，message.content作为备用
             * 2. 历史模式（isStreaming=false）：逐个渲染chunk，数据不完整时用message.content补充
             * 【chunk是AI流式输出的内容片段，不是执行步骤，显示在AI回复区域，不在步骤列表】
             */ }
            {(() => {
              const chunks = message.executionSteps?.filter(step => step.type === "chunk") || [];
              
              // 逐个渲染chunk
              return chunks.map((chunk, index) => {
                const is_reasoning = !!chunk.is_reasoning;
                // 过滤掉 AI 模型返回的特殊标签
                let content = (chunk.content || '').replace(/<\/?longcat_think>/g, '');
                
                // 【小新修复 2026-03-14】判断是否需要在前面加换行
                // 当 is_reasoning 从 true->false 或 false->true 切换时
                if (index > 0) {
                  const prevChunk = chunks[index - 1];
                  const prevIsReasoning = !!prevChunk.is_reasoning;
                  const prevContent = prevChunk.content || '';
                  
                  // 只有在切换时才处理
                  if (is_reasoning !== prevIsReasoning) {
                    // 检查前一个chunk是否以\n结尾
                    if (!prevContent.endsWith('\n')) {
                      // 在当前chunk前面加换行
                      content = '\n' + content;
                    }
                  }
                }
                
                return (
                  <span
                    key={`chunk-${index}`}
                    style={{
                      color: is_reasoning ? '#888' : '#000',
                      fontStyle: is_reasoning ? 'italic' : 'normal',
                      fontSize: is_reasoning ? '0.95em' : '1em',
                    }}
                  >
                    {content}
                  </span>
                );
              });
            })()}

             {/* 【小新修改 2026-03-18】content 回退逻辑：当没有 chunk 时显示 message.content */}
             {/* 【小强修改 2026-04-03】跳过 "🤔 AI 正在思考..." 占位文本（已由 DynamicStatusDisplay 处理） */}
             {(() => {
               let hasAction = 0;
               for (const step of (message.executionSteps || [])) {
                 if (step.type === 'action_tool') {
                   hasAction = 1;
                   break;
                 }
                 if (step.type === 'chunk') {
                   hasAction = 0;
                 }
               }
               
               if (hasAction !== 1) {
                 const chunks = message.executionSteps?.filter(s => s.type === "chunk") || [];
                 const hasFalseReasoning = chunks.some(c => c.is_reasoning === false);
                 
                 const hasErrorStep = message.executionSteps?.some(step => {
                   const content = step.content || '';
                   return step.type === 'error' || 
                          content.includes('[错误]') || 
                          content.includes('429') || 
                          content.includes('限流');
                 });
                 
                 if (hasErrorStep) {
                   return false;
                 }
                 
                 if (message.isStreaming) {
                   // 【小强修改】跳过占位文本，由 DynamicStatusDisplay 处理
                   if (message.content === "🤔 AI 正在思考...") {
                     return false;
                   }
                   return chunks.length === 0;
                 }
                 
                 return !hasFalseReasoning;
               }
               
               return false;
              })() && (
               <div
                 style={{
                   wordBreak: "break-word",
                   overflowWrap: "break-word",
                   paddingRight: 32,
                 }}
               >
                 {message.content && typeof message.content === 'string' 
                   ? message.content.replace(/\n\n/g, '\n')
                   : String(message.content || '').replace(/\n\n/g, '\n')}
               </div>
             )}

            {/* 【小强新增 2026-04-03】动态状态提示：根据 step type 显示对应状态 */}
            {/* 只在 AI 助手消息的气泡底部显示，用户消息不显示 */}
            {!isUser && !isSystem && message.isStreaming && (
              <DynamicStatusDisplay 
                executionSteps={message.executionSteps || []}
                isStreaming={message.isStreaming}
              />
            )}
          </>

          {/* CSS 动画 */}
          {(message.content === "🤔 AI 正在思考..." && message.isStreaming) ||
          message.isError ||
          message.is_reasoning ? (
            <style>{`
              ${
                message.content === "🤔 AI 正在思考..." && message.isStreaming
                  ? `
                @keyframes thinking-pulse {
                  0%, 100% { opacity: 1; }
                  50% { opacity: 0.6; }
                }
                @keyframes cursor-spin {
                  0% { transform: rotate(0deg); }
                  100% { transform: rotate(360deg); }
                }
                .thinking-message {
                  animation: thinking-pulse 1.5s ease-in-out infinite;
                }
                .thinking-cursor {
                  display: inline-block;
                  animation: cursor-spin 1s linear infinite;
                  opacity: 0.7;
                }
                `
                  : ""
              }
              ${
                message.isError
                  ? `
                @keyframes error-fade-in {
                  from {
                    opacity: 0;
                    transform: translateY(-10px);
                  }
                  to {
                    opacity: 1;
                    transform: translateY(0);
                  }
                }
                .error-message {
                  animation: error-fade-in 0.3s ease-out;
              }
              `
                  : ""
              }
              ${
                message.is_reasoning
                  ? `
                .reasoning-message {
                  color: #888;
                  font-style: italic;
                }
              `
                  : ""
              }
            `}</style>
          ) : null}
        </div>
      </div>

      {/* 右侧头像（仅用户消息） */}
      {isUser && (
        <div style={{ flexShrink: 0, marginTop: 6 }}>
          {getAvatar()}
        </div>
      )}

      {/* CSS 样式 - 悬停显示复制按钮 */}
      <style>{`
        .copy-button {
          opacity: 0 !important;
        }
        div:hover .copy-button {
          opacity: 1 !important;
        }
      `}</style>
    </div>
  );
}, messageItemCompare);

// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装 + 自定义比较函数
// eslint-disable-next-line react/display-name
MessageItem.displayName = 'MessageItem';

export default MessageItem;
