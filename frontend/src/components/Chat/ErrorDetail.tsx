import React from "react";

interface ErrorDetailProps {
  errorType?: string;
  errorCode?: string;
  errorMessage?: string;  // message - 错误消息内容
  errorTimestamp?: string;
  errorDetails?: string;
  errorStack?: string;
  errorRetryable?: boolean;
  errorRetryAfter?: number;
  model?: string;
  provider?: string;
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
  errorCode: _errorCode,  // 【小新修复2026-03-14】保留但不使用（用户无需看到技术错误码）
  errorMessage,
  errorTimestamp,
  errorDetails,
  errorStack,
  errorRetryable,
  errorRetryAfter,
  model,
  provider,
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

      {/* 错误消息 - 突出显示 */}
      {errorMessage && (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            background: "rgba(255, 255, 255, 0.5)",
            borderRadius: 6,
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

        {/* 可重试 */}
        {errorRetryable !== undefined && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap", fontSize: "13px" }}>可重试:</span>
            <span style={{ color: errorRetryable ? "#52c41a" : "#999", fontSize: "13px", fontWeight: 500 }}>
              {errorRetryable ? "是" : "否"}
              {errorRetryable && errorRetryAfter !== undefined && (
                <span style={{ color: "#666", marginLeft: 4 }}>
                  ({errorRetryAfter}秒后)
                </span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* 详情 - 全宽显示 */}
      {errorDetails && (
        <div style={{ marginTop: 12 }}>
          <div style={{ color: "#888", fontSize: "13px", marginBottom: 4 }}>详情:</div>
          <div
            style={{
              padding: "8px 12px",
              background: "rgba(255, 255, 255, 0.3)",
              borderRadius: 6,
              color: "#666",
              fontSize: "13px",
              wordBreak: "break-all",
              lineHeight: 1.5,
            }}
          >
            {errorDetails}
          </div>
        </div>
      )}

      {/* 堆栈 - 折叠显示 */}
      {errorStack && (
        <div style={{ marginTop: 12 }}>
          <details>
            <summary style={{ color: "#888", fontSize: "13px", cursor: "pointer" }}>
              查看堆栈信息
            </summary>
            <pre
              style={{
                margin: "8px 0 0 0",
                padding: "8px 12px",
                background: "rgba(0, 0, 0, 0.03)",
                borderRadius: 6,
                color: "#888",
                fontSize: "12px",
                wordBreak: "break-all",
                maxHeight: "150px",
                overflow: "auto",
                lineHeight: 1.4,
              }}
            >
              {errorStack}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
};

export default ErrorDetail;
