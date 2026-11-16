// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 会话级路由模式选择器(输入区工具条, 不新增页面)。
//   纯受控组件: value/onChange/disabled 全由调用方注入, 本组件零判定 — 小欧-2026-11-16

/**
 * RoutingModePicker —— 建议/自动/严格 三档路由模式选择。
 *
 * 数据源与持久化在 useRoutingMode; 本组件只渲染选项与回传选择(单一职责)。
 */
import React from 'react';
import { Select, Tooltip } from 'antd';
import type { RoutingMode } from '../../hooks/useRoutingMode';

const MODE_LABEL: Record<RoutingMode, string> = {
  suggest: '建议',
  auto: '自动',
  strict: '严格',
};

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
  return (
    <Tooltip title="输入能力路由模式：建议=只提示；自动=自动切换可回退；严格=必备能力缺失时明确告知">
      <Select<RoutingMode>
        size="small"
        value={value}
        onChange={onChange}
        disabled={disabled || loading}
        loading={loading}
        style={{ minWidth: 92 }}
        options={(Object.keys(MODE_LABEL) as RoutingMode[]).map((m) => ({
          value: m,
          label: MODE_LABEL[m],
        }))}
      />
    </Tooltip>
  );
}
