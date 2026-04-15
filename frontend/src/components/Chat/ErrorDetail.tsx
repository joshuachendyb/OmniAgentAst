import React from "react";

interface ErrorDetailProps {
  errorType?: string;
  // 【小沈修改2026-04-15】删除errorCode，统一使用errorMessage
  errorMessage?: string;
  errorTimestamp?: string;
  // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除这些字段
  errorRetryAfter?: number;
  model?: string;
  provider?: string;
  // 【小沈添加2026-04-15】新增recoverable和context
  errorRecoverable?: boolean;
  errorContext?: {
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

/**
 * 错误详情面板组件
 * 显示 error 类型的完整信息（11个字段）
 * @author 小新
 * @update 2026-03-14 美化排版，改为两列布局，增大字体
 * @date 2026-03-13
 */
const ErrorDetail: React.FC<ErrorDetailProps> = ({
  errorType,
  // 【小沈修改2026-04-15】删除errorCode
  errorMessage,
  errorTimestamp,
  // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除
  errorRetryAfter,
  model,
  provider,
  // 【小沈添加2026-04-15】新增recoverable和context
  errorRecoverable,
  errorContext,
}) => {
  // 根据error_type显示不同颜色
  const getColors = () => {
    switch (errorType) {
      case "security_error":
        return {
          background: "rgba(255, 193, 7, 0.1)",
          border: "rgba(255, 193, 7, 0.3)",
          color: "#d48806",
          icon: "⚠️",
          title: "待确认",
        };
      case "agent":
        return {
          background: "rgba(24, 144, 255, 0.1)",
          border: "rgba(24, 144, 255, 0.3)",
          color: "#1890ff",
          icon: "🤖",
          title: "Agent错误",
        };
      case "network":
        return {
          background: "rgba(255, 77, 79, 0.08)",
          border: "rgba(255, 77, 79, 0.2)",
          color: "#cf1322",
          icon: "🌐",
          title: "网络错误",
        };
      case "validation":
        return {
          background: "rgba(255, 77, 79, 0.08)",
          border: "rgba(255, 77, 79, 0.2)",
          color: "#cf1322",
          icon: "⚠️",
          title: "参数错误",
        };
      case "file_system":
        return {
          background: "rgba(255, 77, 79, 0.08)",
          border: "rgba(255, 77, 79, 0.2)",
          color: "#cf1322",
          icon: "📁",
          title: "文件错误",
        };
      case "security":
        return {
          background: "rgba(255, 77, 79, 0.08)",
          border: "rgba(255, 77, 79, 0.2)",
          color: "#cf1322",
          icon: "🔒",
          title: "权限错误",
        };
      case "unknown":
        return {
          background: "rgba(255, 77, 79, 0.08)",
          border: "rgba(255, 77, 79, 0.2)",
          color: "#cf1322",
          icon: "❓",
          title: "未知错误",
        };
      default:
        return {
          background: "rgba(255, 77, 79, 0.08)",
          border: "rgba(255, 77, 79, 0.2)",
          color: "#cf1322",
          icon: "❌",
          title: "错误详情",
        };
    }
  };

  const colors = getColors();

  // 格式化错误类型显示
  const formatErrorType = (type?: string) => {
    const typeMap: Record<string, string> = {
      "empty_response": "空响应",
      "timeout": "请求超时",
      "network_error": "网络错误",
      "server_error": "服务器错误",
      "rate_limit": "速率限制",
      "authentication_error": "认证失败",
      "authorization_error": "权限不足",
      "validation_error": "参数错误",
      "not_found": "资源不存在",
      "internal_error": "内部错误",
    };
    return typeMap[type || ""] || type || "未知";
  };

  return (
    <div
      style={{
        marginTop: 12,
        padding: "16px",
        background: colors.background,
        borderRadius: 8,
        border: `1px solid ${colors.border}`,
        fontSize: "14px", // 【小新修改】增大字体
        color: colors.color,
      }}
    >
      {/* 错误类型标题 */}
      <div
        style={{
          fontWeight: 600,
          marginBottom: 12,
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: "15px", // 【小新修改】标题更大
          borderBottom: `1px solid ${colors.border}`,
          paddingBottom: 8,
        }}
      >
        <span>{colors.icon}</span>
        <span>{colors.title}</span>
      </div>

      {/* 错误消息 - 简化显示 */}
      {errorMessage && (
        <div
          style={{
            marginBottom: 8,
            fontWeight: 500,
            color: colors.color,
            fontSize: "14px",
          }}
        >
          {errorMessage}
        </div>
      )}

      {/* 两列布局的错误信息 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "8px 16px",
        }}
      >
        {/* 类型 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "#888", whiteSpace: "nowrap", fontSize: "13px" }}>类型:</span>
          <code
            style={{
              background:
                errorType === "security_error"
                  ? "rgba(255, 193, 7, 0.2)"
                  : errorType === "agent"
                  ? "rgba(24, 144, 255, 0.2)"
                  : "rgba(255, 77, 79, 0.15)",
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: "13px",
              color: colors.color,
              fontWeight: 500,
            }}
          >
            {formatErrorType(errorType)}
          </code>
        </div>

        {/* 时间 */}
        {errorTimestamp && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap", fontSize: "13px" }}>时间:</span>
            <span style={{ color: "#666", fontSize: "13px" }}>
              {new Date(errorTimestamp).toLocaleString("zh-CN")}
            </span>
          </div>
        )}

        {/* 来源 */}
        {(model || provider) && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, gridColumn: "span 2" }}>
            <span style={{ color: "#888", whiteSpace: "nowrap", fontSize: "13px" }}>来源:</span>
            <span style={{ color: "#666", fontSize: "13px" }}>
              {provider && model 
                ? `${provider} (${model})`
                : provider 
                  ? provider 
                  : model
              }
            </span>
          </div>
        )}

        {/* 【小沈添加2026-04-15】显示recoverable字段（替代后端已删除的retryable） */}
        {errorRecoverable !== undefined && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap", fontSize: "13px" }}>可恢复:</span>
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
        {/* 【小沈添加2026-04-15】显示context字段 */}
        {errorContext && (
          <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(255, 255, 255, 0.3)", borderRadius: 6 }}>
            <div style={{ color: "#888", fontSize: "12px", marginBottom: 4 }}>上下文:</div>
            {errorContext.step && <div style={{ color: "#666", fontSize: "13px" }}>步骤: {errorContext.step}</div>}
            {errorContext.model && <div style={{ color: "#666", fontSize: "13px" }}>模型: {errorContext.model}</div>}
            {errorContext.provider && <div style={{ color: "#666", fontSize: "13px" }}>提供商: {errorContext.provider}</div>}
          </div>
        )}
      </div>
    </div>
  );
};

export default ErrorDetail;
