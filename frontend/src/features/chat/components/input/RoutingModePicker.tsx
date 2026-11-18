// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 会话级路由模式选择器(输入区工具条, 不新增页面)。
//   纯受控组件: value/onChange/disabled 全由调用方注入, 本组件零判定 — 小欧-2026-11-16

// 2026-11-16 小欧 文案修订: 选择器由内部术语改用户语言(建议→仅提示/自动→自动切换),
//   提示改为“能力不足时如何处理”结构化三行, 严格档文案对齐实际行为(明确提示, preflight 不阻断) - 小欧-2026-11-16
// 2026-11-16 小欧 - 宽度收窄: 原 minWidth 96 与同排「附件」按钮宽窄不齐, 改为小控件定宽对齐附件按钮 - 小欧-2026-11-16
// 2026-11-16 小欧 - tip 样式归令牌: 行高/间距/字重改引 LineHeight/Gap/FontWeight, 限宽与同区附件提示卡同口径 - 小欧-2026-11-16

// 2026-11-18 opencode 修正: 严格档文案据实(实际仍降级投递, 原"不静默降级"与实现不符);
//   RoutingMode 改引 types/chat 真源 — opencode-2026-11-18

/**
 * RoutingModePicker —— 建议/自动/严格 三档路由模式选择。
 *
 * 数据源与持久化在 useRoutingMode; 本组件只渲染选项与回传选择(单一职责)。
 */
import React from 'react';
import { Select, Tooltip } from 'antd';
import { FontWeight } from '@/utils/stepStyles';
import { Gap, LineHeight } from '@/theme/spacing';
import type { RoutingMode } from '@/types/chat';

const MODE_LABEL: Record<RoutingMode, string> = {
  suggest: '提示',
  auto: '自动',
  strict: '严格',
};

const MODE_DESC: Record<RoutingMode, string> = {
  suggest: '能力不足时只提示，不切换当前模型（默认）',
  auto: '能力不足时自动切到更合适的模型，可一键回退',
  // 严格档只影响"缺能力时给不给阻断式建议", 不改投递方式、也不拦截发送 ——
  //   原文案"不静默降级"与实现不符(实际仍走文本注入降级) — opencode-2026-11-18
  strict: '把原生能力视为必需，缺能力时明确提示（不自动切换，也不拦截发送）',
};

// 宽度与小号「附件」按钮视觉等宽: Select 文本 28 + 箭头 12 + 内距 7×2 + 边框 2 ≈ 66
const PICKER_W = 66;
// 浮层内容限宽(px): 与同区「附件」提示卡同口径, 避免长短不一的 tip 宽度
const TIP_MAX_W = 280;

interface RoutingModePickerProps {
  value: RoutingMode;
  onChange: (v: RoutingMode) => void;
  disabled?: boolean;
  loading?: boolean;
}

export function RoutingModePicker({
  value,
  onChange,
  disabled,
  loading,
}: RoutingModePickerProps) {
  const modeTip = (
    <div
      style={{
        maxWidth: TIP_MAX_W,
        display: 'flex',
        flexDirection: 'column',
        gap: Gap.STACK,
        lineHeight: LineHeight.BODY,
      }}
    >
      <div>模型输入模态能力不匹配时处理方式</div>
      {(Object.keys(MODE_LABEL) as RoutingMode[]).map((m) => (
        <div key={m}>
          <span style={{ fontWeight: FontWeight.MEDIUM }}>{MODE_LABEL[m]}</span>
          {`：${MODE_DESC[m]}`}
        </div>
      ))}
    </div>
  );
  return (
    <Tooltip title={modeTip}>
      <Select<RoutingMode>
        size="small"
        value={value}
        onChange={onChange}
        disabled={disabled || loading}
        loading={loading}
        style={{ width: PICKER_W }}
        options={(Object.keys(MODE_LABEL) as RoutingMode[]).map((m) => ({
          value: m,
          label: MODE_LABEL[m],
        }))}
      />
    </Tooltip>
  );
}
