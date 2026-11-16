// 编辑历史:
// 2026-11-16 小欧 新建: 能力路由推荐条(输入区容器, 独立受控组件)。
//   advice 为后端 routing_advice 原值直读(零翻译); switch 渲染"切换"一键动作,
//   revertModel 非空渲染"回退"(auto 模式自动切换后可撤销); keep 且无回退不占位 — 小欧-2026-11-16
// 2026-11-16 小欧 修复: advice 改为可选, 回退入口不再依赖当前建议(自动切换后建议重算为 keep/空,
//   旧实现随建议消失而吞掉回退按钮) — 小欧-2026-11-16

/**
 * RecommendationBar —— 模型能力路由推荐条
 *
 * 数据源: 后端 preflight.routing_advice 原值 {action, model?, reason?, provider?}。本组件零判定,
 * 只按 action 展示文案与动作按钮; 模型切换/回退由调用方注入(走既有模型层能力)。
 */
import React from 'react';
import { Colors } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';
import type { RoutingAdvice } from '@/types/chat';

interface RecommendationBarProps {
  advice?: RoutingAdvice | null;
  /** switch 一键切换: 由调用方解析 provider 并落库(本组件不碰模型层) */
  onSwitch?: (model: string) => void;
  /** auto 模式回退: 撤回到原模型 */
  onRevert?: () => void;
  /** 非空 = 当前处于自动切换后状态, 展示回退入口(独立于 advice, 建议消失仍可回退) */
  revertModel?: string;
}

export function RecommendationBar({
  advice,
  onSwitch,
  onRevert,
  revertModel,
}: RecommendationBarProps) {
  const a = advice && advice.action !== 'keep' ? advice : null;
  if (!a && !revertModel) return null;
  const text = a
    ? a.reason ||
      (a.action === 'switch'
        ? `推荐切换至 ${a.model ?? ''}`
        : '当前模型能力不足，将降级处理')
    : '';
  const switchModel = a?.action === 'switch' ? a.model : undefined;
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
      {text && <span>{text}</span>}
      {switchModel && onSwitch && (
        <button
          type="button"
          style={buttonStyle}
          onClick={() => onSwitch(switchModel)}
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
