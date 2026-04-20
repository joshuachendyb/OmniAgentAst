/* eslint-disable react/prop-types */
import React, { memo, useMemo } from "react";

interface ErrorDetailProps {
  errorType?: string;
  errorMessage?: string;
  errorTimestamp?: string;
  errorDetails?: string;
  errorStack?: string;
  errorRetryAfter?: number;
  model?: string;
  provider?: string;
  errorRecoverable?: boolean;
  errorContext?: {
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

// ========== Step 2: 外部颜色配置常量 ==========
const ERROR_COLORS_MAP: Record<string, { background: string; border: string; color: string; icon: string; title: string }> = {
  security_error: {
    background: "rgba(255, 193, 7, 0.1)",
    border: "rgba(255, 193, 7, 0.3)",
    color: "#d48806",
    icon: "⚠️",
    title: "待确认",
  },
  agent: {
    background: "rgba(24, 144, 255, 0.1)",
    border: "rgba(24, 144, 255, 0.3)",
    color: "#1890ff",
    icon: "🤖",
    title: "Agent错误",
  },
  network: {
    background: "rgba(255, 77, 79, 0.08)",
    border: "rgba(255, 77, 79, 0.2)",
    color: "#cf1322",
    icon: "🌐",
    title: "网络错误",
  },
  validation: {
    background: "rgba(255, 77, 79, 0.08)",
    border: "rgba(255, 77, 79, 0.2)",
    color: "#cf1322",
    icon: "⚠️",
    title: "参数错误",
  },
  file_system: {
    background: "rgba(255, 77, 79, 0.08)",
    border: "rgba(255, 77, 79, 0.2)",
    color: "#cf1322",
    icon: "📁",
    title: "文件错误",
  },
  security: {
    background: "rgba(255, 77, 79, 0.08)",
    border: "rgba(255, 77, 79, 0.2)",
    color: "#cf1322",
    icon: "🔒",
    title: "权限错误",
  },
  unknown: {
    background: "rgba(255, 77, 79, 0.08)",
    border: "rgba(255, 77, 79, 0.2)",
    color: "#cf1322",
    icon: "❓",
    title: "未知错误",
  },
  default: {
    background: "rgba(255, 77, 79, 0.08)",
    border: "rgba(255, 77, 79, 0.2)",
    color: "#cf1322",
    icon: "❌",
    title: "错误详情",
  },
};

// ========== Step 3: 外部类型标签映射常量 ==========
const ERROR_TYPE_LABELS: Record<string, string> = {
  empty_response: "空响应",
  timeout: "请求超时",
  network_error: "网络错误",
  server_error: "服务器错误",
  rate_limit: "速率限制",
  authentication_error: "认证失败",
  authorization_error: "权限不足",
  validation_error: "参数错误",
  not_found: "资源不存在",
  internal_error: "内部错误",
};

// ========== Step 4: 合并内联style常量 ==========
const containerStyle: React.CSSProperties = {
  marginTop: 12,
  padding: "16px",
  borderRadius: 8,
  fontSize: "14px",
};

const headerStyle: React.CSSProperties = {
  fontWeight: 600,
  marginBottom: 12,
  display: "flex",
  alignItems: "center",
  gap: 8,
  fontSize: "15px",
  paddingBottom: 8,
};

const messageStyle: React.CSSProperties = {
  marginBottom: 8,
  fontWeight: 500,
  fontSize: "14px",
};

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, 1fr)",
  gap: "8px 16px",
};

const labelStyle: React.CSSProperties = {
  color: "#888",
  whiteSpace: "nowrap",
  fontSize: "13px",
};

const valueStyle: React.CSSProperties = {
  color: "#666",
  fontSize: "13px",
};

const codeBlockStyle: React.CSSProperties = {
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: "13px",
  fontWeight: 500,
};

const contextBoxStyle: React.CSSProperties = {
  marginTop: 8,
  padding: "8px 12px",
  background: "rgba(255, 255, 255, 0.3)",
  borderRadius: 6,
};

const detailsBoxStyle: React.CSSProperties = {
  color: "#888",
  fontSize: "12px",
  marginBottom: 4,
};

const contentBoxStyle: React.CSSProperties = {
  color: "#666",
  fontSize: "13px",
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
};

const stackPreStyle: React.CSSProperties = {
  margin: "8px 0 0 0",
  padding: "8px 12px",
  background: "rgba(0, 0, 0, 0.03)",
  borderRadius: 6,
  color: "#888",
  fontSize: "12px",
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  maxHeight: "150px",
  overflow: "auto",
};

// ========== Step 1 + Step 5: 组件使用 memo + useMemo ==========
const ErrorDetail: React.FC<ErrorDetailProps> = memo(({
  errorType,
  errorMessage,
  errorTimestamp,
  errorDetails,
  errorStack,
  errorRetryAfter,
  model,
  provider,
  errorRecoverable,
  errorContext,
}) => {
  // 使用 useMemo 缓存颜色配置
  const colors = useMemo(() => {
    return ERROR_COLORS_MAP[errorType || ""] || ERROR_COLORS_MAP.default;
  }, [errorType]);

  // 格式化错误类型显示
  const formatErrorType = (type?: string) => {
    return ERROR_TYPE_LABELS[type || ""] || type || "未知";
  };

  // 动态code背景色
  const codeBackground = errorType === "security_error"
    ? "rgba(255, 193, 7, 0.2)"
    : errorType === "agent"
    ? "rgba(24, 144, 255, 0.2)"
    : "rgba(255, 77, 79, 0.15)";

  return (
    <div
      style={{
        ...containerStyle,
        background: colors.background,
        border: `1px solid ${colors.border}`,
        color: colors.color,
      }}
    >
      {/* 错误类型标题 */}
      <div
        style={{
          ...headerStyle,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        <span>{colors.icon}</span>
        <span>{colors.title}</span>
      </div>

      {/* 错误消息 - 简化显示 */}
      {errorMessage && (
        <div style={{ ...messageStyle, color: colors.color }}>
          {errorMessage}
        </div>
      )}

      {/* 两列布局的错误信息 */}
      <div style={gridStyle}>
        {/* 类型 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={labelStyle}>类型:</span>
          <code
            style={{
              ...codeBlockStyle,
              background: codeBackground,
              color: colors.color,
            }}
          >
            {formatErrorType(errorType)}
          </code>
        </div>

        {/* 时间 */}
        {errorTimestamp && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={labelStyle}>时间:</span>
            <span style={valueStyle}>
              {new Date(errorTimestamp).toLocaleString("zh-CN")}
            </span>
          </div>
        )}

        {/* 来源 */}
        {(model || provider) && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, gridColumn: "span 2" }}>
            <span style={labelStyle}>来源:</span>
            <span style={valueStyle}>
              {provider && model
                ? `${provider} (${model})`
                : provider
                ? provider
                : model}
            </span>
          </div>
        )}

        {/* 显示recoverable字段 */}
        {errorRecoverable !== undefined && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={labelStyle}>可恢复:</span>
            <span style={{ color: errorRecoverable ? "#52c41a" : "#999", fontSize: "13px", fontWeight: 500 }}>
              {errorRecoverable ? "是" : "否"}
              {errorRecoverable && errorRetryAfter !== undefined && (
                <span style={{ color: "#666", marginLeft: 4 }}>
                  ({errorRetryAfter}秒后)
                </span>
              )}
            </span>
          </div>
        )}

        {/* 显示context字段 */}
        {errorContext && (
          <div style={{ ...contextBoxStyle, gridColumn: "span 2" }}>
            <div style={detailsBoxStyle}>上下文:</div>
            {errorContext.step && <div style={contentBoxStyle}>步骤: {errorContext.step}</div>}
            {errorContext.model && <div style={contentBoxStyle}>模型: {errorContext.model}</div>}
            {errorContext.provider && <div style={contentBoxStyle}>提供商: {errorContext.provider}</div>}
          </div>
        )}

        {/* 显示details字段 */}
        {errorDetails && (
          <div style={{ ...contextBoxStyle, gridColumn: "span 2" }}>
            <div style={detailsBoxStyle}>详情:</div>
            <div style={contentBoxStyle}>{errorDetails}</div>
          </div>
        )}

        {/* 显示stack字段（折叠显示） */}
        {errorStack && (
          <details style={{ marginTop: 8, gridColumn: "span 2" }}>
            <summary style={{ color: "#888", fontSize: "13px", cursor: "pointer" }}>
              查看堆栈信息
            </summary>
            <pre style={stackPreStyle}>{errorStack}</pre>
          </details>
        )}
      </div>
    </div>
  );
});

ErrorDetail.displayName = "ErrorDetail";

export default ErrorDetail;