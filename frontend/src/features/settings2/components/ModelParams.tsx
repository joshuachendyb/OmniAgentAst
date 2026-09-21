// 编辑历史: 2026-09-20 小强 - 新建：模型参数区（跟随当前模型+范围+[已修改]+[重置为默认]确认内联）
// 2026-09-21 小欧 - P0-4+P0-6+P0-7：色/字号→令牌、滑块宽→settingsControl、标签宽→settingsSpacing（[58] P0-4/P0-6/P0-7）
// 2026-09-21 小欧 - 全文逐章核查：gap 裸数字 → Spacing.MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小强 - 设置页17问题复核修复：env 接管键禁用控件+EnvTag 标识（杜绝改假值/假保存/切走丢失）；
//   行 flexWrap 防窄屏溢出（[设置页UI审计] 问题2/16）
import React from 'react';
import { InputNumber, Slider } from 'antd';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import {
  settingsSpacing,
  settingsControl,
  settingsRowLayout,
} from '@/theme/settingsTokens';
import { isDirty } from '../utils/modelUtils';
import { DirtyDot, EnvTag } from './icons';

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
        // 修正(2026-09-21 小强)：env 接管键禁用控件 + EnvTag 标识——
        // 原可编辑但 setParam 写入被 isDirty 排除，静默无效（改假值/保存假成功/切走丢失）([设置页UI审计] 问题2)
        const envKey = envOverride[key];
        return (
          <div
            key={key}
            style={{
              display: settingsRowLayout.display,
              alignItems: settingsRowLayout.alignItems,
              flexWrap: 'wrap',
              gap: settingsRowLayout.gap,
              minHeight: settingsRowLayout.minHeight,
            }}
          >
            <span style={{ width: settingsSpacing.labelWidth }}>
              {key} {envKey && <EnvTag />}
            </span>
            {range ? (
              <span
                style={{
                  display: 'inline-flex',
                  gap: Spacing.MD,
                  alignItems: 'center',
                }}
              >
                <Slider
                  min={range.min}
                  max={range.max}
                  value={value}
                  disabled={envKey}
                  style={{ width: settingsControl.sliderWidth }}
                  onChange={(v) => onChange(key, v)}
                />
                <InputNumber
                  min={range.min}
                  max={range.max}
                  value={value}
                  disabled={envKey}
                  onChange={(v) => onChange(key, v)}
                />
              </span>
            ) : (
              <InputNumber
                value={value}
                disabled={envKey}
                onChange={(v) => onChange(key, v)}
              />
            )}
            <span
              style={{
                color: Colors.TEXT.SECONDARY,
                fontSize: FontSize.SECONDARY,
              }}
            >
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
