/**
 * ErrorBoundary - 应用级错误边界（白屏兜底）
 *
 * 捕获子树渲染期抛出的异常（含开发态 Vite react-refresh HMR 对 hooks 数量/顺序变更
 * 触发 "Should have a queue" 的渲染崩溃；生产无 react-refresh 不触发，仅作通用兜底），
 * 用友好提示 + 一键刷新替代整页白屏。正常渲染不介入、零运行时开销。
 *
 * 局限（React 官方语义）：不捕获事件处理器内/异步(定时器/await)/SSR/自身抛出的错误。
 *
 * @author 小欧
 * @date 2026-09-09
 */
// 编辑历史: 2026-09-09 小欧 - 新建: App 根部错误边界, 渲染期异常从"整页白屏"降级为
//   Result 提示 + 一键刷新; 由 dev HMR hook 变更崩溃场景驱动落地(拉一根捕获链) — 小欧-2026-09-09
import React from 'react';
import { Button, Result } from 'antd';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false, message: '' };

  // 渲染期抛错 → 触发 fallback 渲染
  static getDerivedStateFromError(error: unknown): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : String(error),
    };
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    // 2016-2026: 错误详情与组件栈落 console, 供开发/反馈排查, 不吞静默
    console.error('[ErrorBoundary] 捕获渲染异常:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            padding: 24,
          }}
        >
          <Result
            status="error"
            title="页面出现异常"
            subTitle={
              this.state.message || '渲染过程中发生了意外错误，请刷新页面重试'
            }
            extra={
              <Button type="primary" onClick={() => window.location.reload()}>
                刷新页面
              </Button>
            }
          />
        </div>
      );
    }
    return this.props.children;
  }
}

export { ErrorBoundary };
