/* eslint-disable react/prop-types */
// 编辑历史: 2026-08-26 小欧 - 参与P1-P7: 错误详情组件(任务信息条错误展示)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 引入formatSafeTimestamp; formatErrorType提顶层; 来源/上下文注释澄清
// 编辑历史: 2026-08-27 小欧 - 修复chat-E: errorType 形如 network_error 需对齐配色键(network 等), 剥离 _error 后缀查表(BUG-E)
import React, { memo } from 'react';
import { formatSafeTimestamp } from '../../utils/formatSafeTimestamp'; // 2026-08-27 小欧 三堂会审: 复用时戳安全格式化(复用优先)

interface ErrorDetailProps {
  errorType?: string;
  errorMessage?: string;
  errorTimestamp?: string;
  errorDetails?: string;
  errorStack?: string;

  model?: string;
  provider?: string;
  errorContext?: {
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

// ========== 错误类型格式化纯函数（模块顶层，2026-08-27 小欧 三堂会审） ==========
// 2026-08-27 小欧 三堂会审: 提到模块顶层保持纯函数, 与上方常量同区, 便于复用与测试
const formatErrorType = (type?: string): string => {
  return ERROR_TYPE_LABELS[type || ''] || type || '未知';
};

// ========== Step 2: 外部颜色配置常量 ==========
// 2026-08-27 小欧 三堂会审B36: codeBackground纳入配置, 消除三元嵌套散落
const ERROR_COLORS_MAP: Record<
  string,
  {
    background: string;
    border: string;
    color: string;
    icon: string;
    title: string;
    codeBackground: string;
  }
> = {
  security_error: {
    background: 'rgba(255, 193, 7, 0.1)',
    border: 'rgba(255, 193, 7, 0.3)',
    color: '#d48806',
    icon: '⚠️',
    title: '待确认',
    codeBackground: 'rgba(255, 193, 7, 0.2)',
  },
  agent: {
    background: 'rgba(24, 144, 255, 0.1)',
    border: 'rgba(24, 144, 255, 0.3)',
    color: '#1677ff',
    icon: '🤖',
    title: 'Agent错误',
    codeBackground: 'rgba(24, 144, 255, 0.2)',
  },
  network: {
    background: 'rgba(255, 77, 79, 0.08)',
    border: 'rgba(255, 77, 79, 0.2)',
    color: '#cf1322',
    icon: '🌐',
    title: '网络错误',
    codeBackground: 'rgba(255, 77, 79, 0.15)',
  },
  validation: {
    background: 'rgba(255, 77, 79, 0.08)',
    border: 'rgba(255, 77, 79, 0.2)',
    color: '#cf1322',
    icon: '⚠️',
    title: '参数错误',
    codeBackground: 'rgba(255, 77, 79, 0.15)',
  },
  file_system: {
    background: 'rgba(255, 77, 79, 0.08)',
    border: 'rgba(255, 77, 79, 0.2)',
    color: '#cf1322',
    icon: '📁',
    title: '文件错误',
    codeBackground: 'rgba(255, 77, 79, 0.15)',
  },
  security: {
    background: 'rgba(255, 77, 79, 0.08)',
    border: 'rgba(255, 77, 79, 0.2)',
    color: '#cf1322',
    icon: '🔒',
    title: '权限错误',
    codeBackground: 'rgba(255, 77, 79, 0.15)',
  },
  unknown: {
    background: 'rgba(255, 77, 79, 0.08)',
    border: 'rgba(255, 77, 79, 0.2)',
    color: '#cf1322',
    icon: '❓',
    title: '未知错误',
    codeBackground: 'rgba(255, 77, 79, 0.15)',
  },
  default: {
    background: 'rgba(255, 77, 79, 0.08)',
    border: 'rgba(255, 77, 79, 0.2)',
    color: '#cf1322',
    icon: '❌',
    title: '错误详情',
    codeBackground: 'rgba(255, 77, 79, 0.15)',
  },
};

// ========== Step 3: 外部类型标签映射常量 ==========
const ERROR_TYPE_LABELS: Record<string, string> = {
  empty_response: '空响应',
  timeout: '请求超时',
  network_error: '网络错误',
  server_error: '服务器错误',
  rate_limit: '速率限制',
  authentication_error: '认证失败',
  authorization_error: '权限不足',
  validation_error: '参数错误',
  not_found: '资源不存在',
  internal_error: '内部错误',
};

// ========== Step 4: 合并内联style常量 ==========
const containerStyle: React.CSSProperties = {
  marginTop: 12,
  padding: '16px',
  borderRadius: 8,
  fontSize: '14px',
};

const headerStyle: React.CSSProperties = {
  fontWeight: 600,
  marginBottom: 12,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: '15px',
  paddingBottom: 8,
};

const messageStyle: React.CSSProperties = {
  marginBottom: 8,
  fontWeight: 500,
  fontSize: '14px',
};

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gap: '8px 16px',
};

const labelStyle: React.CSSProperties = {
  color: '#888',
  whiteSpace: 'nowrap',
  fontSize: '13px',
};

const valueStyle: React.CSSProperties = {
  color: '#666',
  fontSize: '13px',
};

const codeBlockStyle: React.CSSProperties = {
  padding: '2px 8px',
  borderRadius: 4,
  fontSize: '13px',
  fontWeight: 500,
};

const contextBoxStyle: React.CSSProperties = {
  marginTop: 8,
  padding: '8px 12px',
  background: 'rgba(255, 255, 255, 0.3)',
  borderRadius: 6,
};

const detailsBoxStyle: React.CSSProperties = {
  color: '#888',
  fontSize: '12px',
  marginBottom: 4,
};

const contentBoxStyle: React.CSSProperties = {
  color: '#666',
  fontSize: '13px',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
};

const stackPreStyle: React.CSSProperties = {
  margin: '8px 0 0 0',
  padding: '8px 12px',
  background: 'rgba(0, 0, 0, 0.03)',
  borderRadius: 6,
  color: '#888',
  fontSize: '12px',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
  maxHeight: '150px',
  overflow: 'auto',
};

// ========== Step 1 + Step 5: 组件使用 memo + useMemo ==========
const ErrorDetail: React.FC<ErrorDetailProps> = memo(
  ({
    errorType,
    errorMessage,
    errorTimestamp,
    errorDetails,
    errorStack,

    model,
    provider,
    errorContext,
  }) => {
    // 2026-08-27 小欧 修复: errorType 形如 'network_error'/'validation_error' 需对齐配色键(network/validation); 剥离 _error 后缀查表, 否则回落默认标题(BUG-E)
    const colors =
      ERROR_COLORS_MAP[errorType || ''] ||
      ERROR_COLORS_MAP[(errorType || '').replace(/_error$/, '')] ||
      ERROR_COLORS_MAP.default;

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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={labelStyle}>类型:</span>
            <code
              style={{
                ...codeBlockStyle,
                background: colors.codeBackground,
                color: colors.color,
              }}
            >
              {formatErrorType(errorType)}
            </code>
          </div>

          {/* 时间 */}
          {errorTimestamp && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={labelStyle}>时间:</span>
              <span style={valueStyle}>
                {formatSafeTimestamp(errorTimestamp)}
              </span>
            </div>
          )}

          {/* 来源 */}
          {/* 2026-08-27 小欧 三堂会审: 顶层model/provider = 错误来源展示(顶层上下文) */}
          {(model || provider) && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                gridColumn: 'span 2',
              }}
            >
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

          {/* 显示context字段 */}
          {errorContext && (
            <div style={{ ...contextBoxStyle, gridColumn: 'span 2' }}>
              <div style={detailsBoxStyle}>上下文:</div>
              {errorContext.step && (
                <div style={contentBoxStyle}>步骤: {errorContext.step}</div>
              )}
              {/* 2026-08-27 小欧 三堂会审: errorContext.model/provider = 出错步骤内的上下文(非顶层来源) */}
              {errorContext.model && (
                <div style={contentBoxStyle}>模型: {errorContext.model}</div>
              )}
              {errorContext.provider && (
                <div style={contentBoxStyle}>
                  提供商: {errorContext.provider}
                </div>
              )}
            </div>
          )}

          {/* 显示details字段 */}
          {errorDetails && (
            <div style={{ ...contextBoxStyle, gridColumn: 'span 2' }}>
              <div style={detailsBoxStyle}>详情:</div>
              <div style={contentBoxStyle}>{errorDetails}</div>
            </div>
          )}

          {/* 显示stack字段（折叠显示） */}
          {errorStack && (
            <details style={{ marginTop: 8, gridColumn: 'span 2' }}>
              <summary
                style={{ color: '#888', fontSize: '13px', cursor: 'pointer' }}
              >
                查看堆栈信息
              </summary>
              <pre style={stackPreStyle}>{errorStack}</pre>
            </details>
          )}
        </div>
      </div>
    );
  }
);

ErrorDetail.displayName = 'ErrorDetail';

export default ErrorDetail;
