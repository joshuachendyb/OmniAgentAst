/**
 * 动态状态提示组件
 *
 * 根据 executionSteps 动态显示当前 AI 执行状态
 * 支持：图标、文字、计时器、旋转竖线
 *
 * 【重要说明】
 * 这个状态提示显示在 AI 气泡的底部，作用是提示"下一个步骤"的信息。
 * 因为有时候从当前步骤到下一个步骤（比如调用LLM）需要较长时间，给用户一个心理预期。
 *
 * 例如：
 * - 当前是 thought（思考）步骤时，提示"Agent 正在执行工具" → 下一个是 action
 * - 当前是 action（执行工具）步骤时，提示"Agent 正在执行观察" → 下一个是 observation
 * - 当前是 observation（观察结果）步骤时，提示"AI 正在思考" → 下一个是 thought（再次调用LLM）
 *
 * 所以这里的文字不是描述当前步骤，而是描述下一个步骤！不要改错了！
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-03
 *
 * 编辑历史:
 * 2026-07-18 小欧 FinalStep终态规整: statusConfig加failed key; deriveStatus按outcome分流cancelled/failed
 *   【病根】原statusConfig无failed key, outcome=failed时fallback到waiting→显示🚀而非❌;
 *          deriveStatus读type=final统一返回'final'→无法区分failed终态。
 *   【改法】①statusConfig加failed:{icon:'❌',text:'AI任务执行失败'}
 *          ②deriveStatus: final+cancelled→'cancelled', final+failed→'failed', final+completed→'final'
 *          ③删旧type=cancelled分支(已废弃)
 */

import React, { useState, useEffect } from 'react';

// 状态配置表
// 【重要】这里的 text 描述的是"下一个步骤"，不是当前步骤！
// 例如：thought 步骤时显示的是"下一个是 action"，action 步骤时显示的是"下一个是 observation"
const statusConfig: Record<
  string,
  { icon: string; text: string; animate: boolean }
> = {
  waiting: { icon: '🚀', text: 'AI开始执行任务', animate: true },
  start: { icon: '🤔', text: 'AI 正在思考', animate: true },
  thought: { icon: '🛠️', text: 'Agent 正在执行"tool_name"', animate: true },
  action: {
    icon: '👁️',
    text: 'Agent 正在执行"observation"',
    animate: true,
  },
  observation: { icon: '🤔', text: 'AI 正在思考', animate: true },
  chunk: { icon: '💬', text: 'AI 正在回复', animate: true },
  final: { icon: '✅', text: 'AI任务执行完成', animate: false },
  error: { icon: '❌', text: 'AI任务执行出错', animate: false }, // 小欧 2026-07-13: error 不可映射为 final(✅), 否则错误被误显为成功
  failed: { icon: '❌', text: 'AI任务执行失败', animate: false }, // 2026-07-18 小欧 FinalStep终态规整: outcome=failed 终态须显❌, 禁止误显为完成(waiting)
  disconnected: { icon: '⚠️', text: '连接已中断', animate: false },
  cancelled: { icon: '⚠️', text: '任务已取消', animate: false },
  paused: { icon: '⏸️', text: '任务已暂停', animate: false },
  retrying: { icon: '🔄', text: '正在重试...', animate: true },
  resumed: { icon: '▶️', text: '任务已恢复', animate: false },
};

// 格式化时间：秒 → MM:SS
const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
};

// 从 executionSteps 派生当前状态
// 2026-07-18 小欧 FinalStep 终态规整：终态统一 type=final，由 outcome 声明 cancelled/failed/completed
const deriveStatus = (
  executionSteps: Array<{ type: string; outcome?: string }>
): string => {
  if (!executionSteps || executionSteps.length === 0) {
    return 'waiting';
  }

  const lastStep = executionSteps[executionSteps.length - 1];
  const hasChunk = executionSteps.some((s) => s.type === 'chunk');

  if (lastStep.type === 'error') {
    return 'error'; // 小欧 2026-07-13: error 与 final 严格区分, 错误态显示❌而非✅
  }
  if (lastStep.type === 'final') {
    // 2026-07-18 小欧 终态统一 FinalStep：取消/失败必须按 outcome 分流，禁止误显为完成
    if (lastStep.outcome === 'cancelled') {
      return 'cancelled';
    }
    if (lastStep.outcome === 'failed') {
      return 'failed';
    }
    return 'final';
  }
  // 2026-07-18 小欧 旧 type=cancelled 数据已废弃（不向后兼容），落入下方默认
  if (lastStep.type === 'paused') {
    return 'paused';
  }
  if (lastStep.type === 'retrying') {
    return 'retrying';
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
      setElapsedSeconds((s) => s + 1);
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
          /* 方案A：脉冲圆点 */
          @keyframes status-dot-pulse {
            0%, 100% { 
              opacity: 1;
              transform: scale(1);
            }
            50% { 
              opacity: 0.4;
              transform: scale(0.6);
            }
          }
          /* 方案B：波浪线 */
          @keyframes status-wave {
            0%, 100% { transform: translateY(0); opacity: 0.6; }
            25% { transform: translateY(-3px); opacity: 1; }
            75% { transform: translateY(3px); opacity: 1; }
          }
          /* 方案C：三点跳动 */
          @keyframes status-dot-bounce-1 {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
            30% { transform: translateY(-6px); opacity: 1; }
          }
          @keyframes status-dot-bounce-2 {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
            40% { transform: translateY(-6px); opacity: 1; }
          }
          @keyframes status-dot-bounce-3 {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
            50% { transform: translateY(-6px); opacity: 1; }
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
          /* 旋转竖线 */
          .status-cursor {
            display: inline-block;
            font-size: 0.85em;
            color: #1890ff;
            animation: status-cursor-combo 1.2s ease-in-out infinite;
          }
          /* 脉冲圆点 */
          .status-dot-pulse {
            display: inline-block;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #1890ff;
            animation: status-dot-pulse 1s ease-in-out infinite;
          }
          /* 波浪线 */
          .status-wave {
            display: inline-block;
            color: #1890ff;
            font-weight: bold;
            animation: status-wave 1s ease-in-out infinite;
          }
          /* 三点跳动 */
          .status-dot-bounce {
            display: inline-flex;
            align-items: center;
            gap: 2px;
          }
          .status-dot-bounce span {
            display: inline-block;
            width: 4px;
            height: 4px;
            border-radius: 50%;
            background: #1890ff;
          }
          .status-dot-bounce span:nth-child(1) {
            animation: status-dot-bounce-1 1.4s ease-in-out infinite;
          }
          .status-dot-bounce span:nth-child(2) {
            animation: status-dot-bounce-2 1.4s ease-in-out infinite;
          }
          .status-dot-bounce span:nth-child(3) {
            animation: status-dot-bounce-3 1.4s ease-in-out infinite;
          }
        `}</style>
        <span className="status-text">
          {config.icon} {config.text}{' '}
          <span className="status-timer">{formatTime(elapsedSeconds)}</span>
          {/* 四种动画对比展示 */}
          <span
            style={{
              marginLeft: '1em',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '1.5em',
            }}
          >
            <span className="status-cursor">▌</span>
            <span className="status-dot-pulse" />
            <span className="status-wave">〜</span>
            <span className="status-dot-bounce">
              <span />
              <span />
              <span />
            </span>
          </span>
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
