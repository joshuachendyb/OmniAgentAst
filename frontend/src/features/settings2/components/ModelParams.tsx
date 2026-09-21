// 编辑历史: 2026-09-20 小强 - 新建：模型参数区（跟随当前模型+范围+[已修改]+[重置为默认]确认内联）
// 2026-09-21 小欧 - P0-4+P0-6+P0-7：色/字号→令牌、滑块宽→settingsControl、标签宽→settingsSpacing（[58] P0-4/P0-6/P0-7）
import React from 'react';
import { InputNumber, Slider } from 'antd';
import { Colors, FontSize } from '@/utils/stepStyles';
import { settingsSpacing, settingsControl, settingsRowLayout } from '@/theme/settingsTokens';
import { isDirty } from '../utils/modelUtils';
import { DirtyDot } from './icons';

interface Props {
  params: Record<string, unknown>;
  defaults: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  envOverride: Record<string, boolean>;
  onChange: (key: string, value: unknown) => void;
}

export const ModelParams: React.FC<Props> = ({
  params,
  defaults,
  ranges,
  envOverride,
  onChange,
}) => {
  const dirty = isDirty(params, defaults, envOverride);
  return (
    <div>
      {Object.keys(defaults).map((key) => {
        const range = ranges[key];
        const value = (params[key] ?? defaults[key]) as number;
        return (
          <div
            key={key}
            style={{
              display: settingsRowLayout.display,
              alignItems: settingsRowLayout.alignItems,
              gap: settingsRowLayout.gap,
              minHeight: settingsRowLayout.minHeight,
            }}
          >
            <span style={{ width: settingsSpacing.labelWidth }}>{key}</span>
            {range ? (
              <span
                style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}
              >
                <Slider
                  min={range.min}
                  max={range.max}
                  value={value}
                  style={{ width: settingsControl.sliderWidth }}
                  onChange={(v) => onChange(key, v)}
                />
                <InputNumber
                  min={range.min}
                  max={range.max}
                  value={value}
                  onChange={(v) => onChange(key, v)}
                />
              </span>
            ) : (
              <InputNumber value={value} onChange={(v) => onChange(key, v)} />
            )}
            <span style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.SECONDARY }}>
              范围{range ? `${range.min}-${range.max}` : '不限'} 默认
              {String(defaults[key])}
            </span>
            {dirty[key] && <DirtyDot />}
          </div>
        );
      })}
    </div>
  );
};
