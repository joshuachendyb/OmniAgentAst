/**
 * 动态状态提示组件
 * 
 * 根据 executionSteps 动态显示当前 AI 执行状态
 * 支持：图标、文字、计时器、旋转竖线
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-03
 */

import React, { useState, useEffect, useMemo } from 'react';

// 状态配置表
const statusConfig: Record<string, { icon: string; text: string; animate: boolean }> = {
  waiting:     { icon: '🚀', text: 'AI开始执行任务', animate: true },
  start:       { icon: '🤔', text: 'AI 正在思考', animate: true },
  thought:     { icon: '🛠️', text: 'Agent 正在执行"action_tool"', animate: true },
  action_tool: { icon: '👁️', text: 'Agent 正在执行"observation"', animate: true },
  observation: { icon: '🤔', text: 'AI 正在思考', animate: true },
  chunk:       { icon: '💬', text: 'AI 正在回复', animate: true },
  final:       { icon: '✅', text: 'AI任务执行完成', animate: false },
  error:       { icon: '✅', text: 'AI任务执行完成', animate: false },
  disconnected:{ icon: '⚠️', text: '连接已中断', animate: false },
};

// 格式化时间：秒 → MM:SS
const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
};

// 从 executionSteps 派生当前状态
const deriveStatus = (executionSteps: Array<{ type: string }>): string => {
  if (!executionSteps || executionSteps.length === 0) {
    return 'waiting';
  }
  
  const lastStep = executionSteps[executionSteps.length - 1];
  const hasChunk = executionSteps.some(s => s.type === 'chunk');
  
  if (lastStep.type === 'final' || lastStep.type === 'error') {
    return 'final';
  }
  
  if (hasChunk) {
    return 'chunk';
  }
  
  return lastStep.type;
};

// 组件 Props
interface DynamicStatusDisplayProps {
  executionSteps: Array<{ type: string }>;
  isStreaming: boolean;
  isDisconnected?: boolean;
}

// 动态状态提示组件
export const DynamicStatusDisplay: React.FC<DynamicStatusDisplayProps> = ({
  executionSteps,
  isStreaming,
  isDisconnected = false,
}) => {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  
  // 派生当前状态
  const currentStatus = isDisconnected 
    ? 'disconnected' 
    : deriveStatus(executionSteps);
  
  const config = statusConfig[currentStatus] || statusConfig['waiting'];
  
  // 计时器：状态切换时重置，完成/断线时停止
  useEffect(() => {
    if (!config.animate) {
      return;
    }
    
    setElapsedSeconds(0);
    const timer = setInterval(() => {
      setElapsedSeconds(s => s + 1);
    }, 1000);
    
    return () => clearInterval(timer);
  }, [currentStatus, config.animate]);
  
  // 渲染
  if (config.animate) {
    return (
      <div className="status-display">
        <style>{`
          @keyframes status-text-breathe {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
          }
          @keyframes status-cursor-combo {
            0% { 
              opacity: 1;
              transform: rotate(0deg) scaleY(1);
            }
            25% {
              opacity: 0.7;
              transform: rotate(90deg) scaleY(0.8);
            }
            50% { 
              opacity: 0.3;
              transform: rotate(180deg) scaleY(0.6);
            }
            75% {
              opacity: 0.7;
              transform: rotate(270deg) scaleY(0.8);
            }
            100% { 
              opacity: 1;
              transform: rotate(360deg) scaleY(1);
            }
          }
          .status-text {
            color: #333;
            font-weight: 500;
            animation: status-text-breathe 1.5s ease-in-out infinite;
          }
          .status-timer {
            color: #666;
            font-variant-numeric: tabular-nums;
          }
          .status-cursor {
            display: inline-block;
            font-size: 0.85em;
            color: #1890ff;
            animation: status-cursor-combo 1.2s ease-in-out infinite;
          }
        `}</style>
        <span className="status-text">
          {config.icon} {config.text}{' '}
          <span className="status-timer">{formatTime(elapsedSeconds)}</span>
          <span className="status-cursor" style={{ marginLeft: '2em' }}>▌</span>
        </span>
      </div>
    );
  }
  
  return (
    <div className="status-display">
      <span>
        {config.icon} {config.text}
      </span>
    </div>
  );
};
