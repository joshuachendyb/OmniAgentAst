// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 能力路由推荐条(输入区容器, 独立受控组件)。
//   advice 为后端 routing_advice 原值直读(零翻译); switch 渲染"切换"一键动作,
//   revertModel 非空渲染"回退"(auto 模式自动切换后可撤销); keep 不占位 — 小欧-2026-11-16

/**
 * RecommendationBar —— 模型能力路由推荐条
 *
 * 数据源: 后端 preflight.routing_advice 原值 {action, model?, reason?}。本组件零判定,
 * 只按 action 展示文案与动作按钮; 模型切换/回退由调用方注入(走既有模型层能力)。
 */
import React from 'react';
import { Colors } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';

export interface RoutingAdvice {
  action: 'keep' | 'switch' | 'degrade';
  model?: string;
  reason?: string;
  /** 切换目标 provider(一键切换落 L2 需要) — 小欧-2026-11-16 */
  provider?: string;
}

interface RecommendationBarProps {
  advice: RoutingAdvice;
  /** switch 一键切换: 由调用方解析 provider 并落库(本组件不碰模型层) */
  onSwitch?: (model: string) => void;
  /** auto 模式回退: 撤回到原模型 */
  onRevert?: () => void;
  /** 非空 = 当前处于自动切换后状态, 展示回退入口 */
  revertModel?: string;
}

export function RecommendationBar({
  advice,
  onSwitch,
  onRevert,
  revertModel,
}: RecommendationBarProps) {
  if (advice.action === 'keep') return null;
  const text =
    advice.reason ||
    (advice.action === 'switch'
      ? `推荐切换至 ${advice.model ?? ''}`
      : '当前模型能力不足，将降级处理');
  const canSwitch = advice.action === 'switch' && !!advice.model && !!onSwitch;
  const buttonStyle: React.CSSProperties = {
    marginLeft: 8,
    cursor: 'pointer',
    fontSize: chatTokens.fontSM,
    color: Colors.PRIMARY,
    background: 'none',
    border: 'none',
    padding: 0,
  };
  return (
    <div
      role="note"
      data-testid="routing-bar"
      style={{ color: Colors.TEXT.SECONDARY, fontSize: chatTokens.fontSM }}
    >
      <span>{text}</span>
      {canSwitch && (
        <button
          type="button"
          style={buttonStyle}
          onClick={() => onSwitch(advice.model as string)}
        >
          切换
        </button>
      )}
      {revertModel && onRevert && (
        <button type="button" style={buttonStyle} onClick={onRevert}>
          回退至 {revertModel}
        </button>
      )}
    </div>
  );
}
