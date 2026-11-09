// 编辑历史: 2026-11-09 小欧 - 新建：② 输入模态行（勾选编辑 + 未知值灰标 + 脏点）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { Checkbox, Tag } from 'antd';
import { Colors, Spacing } from '@/utils/stepStyles';
import { settingsRowStyle, settingsLabelStyle } from '@/theme/settingsTokens';
import {
  CAPABILITY_OPTIONS,
  KNOWN_CAPABILITY_VALUES,
  isCapsDirty,
} from '../utils/modelUtils';
import { DirtyDot } from './icons';

interface Props {
  value: string[];
  baseline: string[];
  envManaged: boolean;
  onChange: (value: string[]) => void;
}

export const ModelTabInputModalities: React.FC<Props> = ({
  value,
  baseline,
  envManaged,
  onChange,
}) => (
  <div style={settingsRowStyle}>
    <span style={settingsLabelStyle}>输入模态</span>
    <span style={{ flex: 1 }}>
      <Checkbox.Group
        value={value}
        // env 接管按 providerConfig.env 禁用（后端拒保存）
        disabled={envManaged}
        options={CAPABILITY_OPTIONS}
        onChange={(v) => onChange(v as string[])}
      />
      {/* yaml 手写非枚举值灰色只读 Tag：看得见、本页不提供增删 */}
      {value
        .filter((v) => !KNOWN_CAPABILITY_VALUES.has(v))
        .map((v) => (
          <Tag
            key={v}
            style={{
              cursor: 'not-allowed',
              marginLeft: Spacing.XS,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {v}
          </Tag>
        ))}
    </span>
    {isCapsDirty(value, baseline) && <DirtyDot />}
  </div>
);
