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
 * @date 2026-03-13
 */
const ErrorDetail: React.FC<ErrorDetailProps> = ({
  errorType,
  errorCode,
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

  return (
    <div
      style={{
        marginTop: 12,
        padding: "10px 12px",
        background: colors.background,
        borderRadius: 8,
        border: `1px solid ${colors.border}`,
        fontSize: "0.85em",
        color: colors.color,
      }}
    >
      {/* 错误类型标题 */}
      <div
        style={{
          fontWeight: 600,
          marginBottom: 8,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span>
          {colors.icon} {colors.title}
        </span>
      </div>

      {/* 错误信息表格 */}
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "0.8em",
        }}
      >
        <tbody>
          {errorType && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                }}
              >
                类型:
              </td>
              <td style={{ padding: "2px 0" }}>
                <code
                  style={{
                    background:
                      errorType === "security_error"
                        ? "rgba(255, 193, 7, 0.2)"
                        : errorType === "agent"
                        ? "rgba(24, 144, 255, 0.2)"
                        : "rgba(255, 77, 79, 0.15)",
                    padding: "1px 4px",
                    borderRadius: 3,
                    fontSize: "0.9em",
                    color: colors.color,
                  }}
                >
                  {errorType}
                </code>
              </td>
            </tr>
          )}
          {errorMessage && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                  verticalAlign: "top",
                }}
              >
                消息:
              </td>
              <td
                style={{
                  padding: "2px 0",
                  color: colors.color,
                  fontWeight: 500,
                }}
              >
                {errorMessage}
              </td>
            </tr>
          )}
          {errorCode && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                }}
              >
                错误码:
              </td>
              <td style={{ padding: "2px 0" }}>
                <code
                  style={{
                    background: "rgba(0,0,0,0.05)",
                    padding: "1px 4px",
                    borderRadius: 3,
                    fontSize: "0.9em",
                  }}
                >
                  {errorCode}
                </code>
              </td>
            </tr>
          )}
          {errorTimestamp && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                }}
              >
                时间:
              </td>
              <td style={{ padding: "2px 0", color: "#666" }}>
                {new Date(errorTimestamp).toLocaleString("zh-CN")}
              </td>
            </tr>
          )}
          {model && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                }}
              >
                模型:
              </td>
              <td style={{ padding: "2px 0" }}>{model}</td>
            </tr>
          )}
          {provider && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                }}
              >
                提供商:
              </td>
              <td style={{ padding: "2px 0" }}>{provider}</td>
            </tr>
          )}
          {errorRetryable !== undefined && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                }}
              >
                可重试:
              </td>
              <td style={{ padding: "2px 0" }}>
                {errorRetryable ? "是" : "否"}
                {errorRetryable && errorRetryAfter !== undefined && (
                  <span style={{ color: "#666", marginLeft: 8 }}>
                    (等待 {errorRetryAfter} 秒)
                  </span>
                )}
              </td>
            </tr>
          )}
          {errorDetails && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                  verticalAlign: "top",
                }}
              >
                详情:
              </td>
              <td
                style={{
                  padding: "2px 0",
                  color: "#666",
                  fontSize: "0.85em",
                  wordBreak: "break-all",
                }}
              >
                {errorDetails}
              </td>
            </tr>
          )}
          {errorStack && (
            <tr>
              <td
                style={{
                  padding: "2px 8px 2px 0",
                  color: "#888",
                  whiteSpace: "nowrap",
                  verticalAlign: "top",
                }}
              >
                堆栈:
              </td>
              <td
                style={{
                  padding: "2px 0",
                  color: "#888",
                  fontSize: "0.75em",
                  wordBreak: "break-all",
                  maxHeight: "100px",
                  overflow: "auto",
                }}
              >
                <pre style={{ margin: 0 }}>{errorStack}</pre>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default ErrorDetail;
