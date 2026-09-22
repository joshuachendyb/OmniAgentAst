// 编辑历史: 2026-09-20 小强 - 新建：模型参数区（跟随当前模型+范围+[已修改]+[重置为默认]确认内联）
// 2026-09-21 小欧 - P0-4+P0-6+P0-7：色/字号→令牌、滑块宽→settingsControl、标签宽→settingsSpacing（[58] P0-4/P0-6/P0-7）
// 2026-09-21 小欧 - 全文逐章核查：gap 裸数字 → Spacing.MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小强 - 设置页17问题复核修复：env 接管键禁用控件+EnvTag 标识（杜绝改假值/假保存/切走丢失）；
//   行 flexWrap 防窄屏溢出（[设置页UI审计] 问题2/16）
// 2026-09-22 小欧 - [62]P4 3.2(5) ModelParams 五分支渲染：删 `as number` 类型谎言；rawValue 原值判型 +
//   enumOpts→Select 字符串直绑（禁 indexOf/[idx]）；range→Slider+InputNumber 安全转数字(isNaN 回退 range.min)；
//   number→InputNumber；boolean→Switch；object→TextArea(JSON，blur 失败回退默认)；string→Input。
//   Props 加 options?（枚举选项表）/onReset?（对齐调用方 SettingsPage 已透传的 options）。
import React from 'react';
import { Input, InputNumber, Select, Slider, Switch } from 'antd';
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
  options?: Record<string, string[]>;
  envOverride: Record<string, boolean>;
  onChange: (key: string, value: unknown) => void;
  onReset?: (key: string) => void;
}

export const ModelParams: React.FC<Props> = ({
  params,
  defaults,
  ranges,
  options,
  envOverride,
  onChange,
}) => {
  const dirty = isDirty(params, defaults, envOverride);
  return (
    <div>
      {Object.keys(defaults).map((key) => {
        const range = ranges[key];
        const rawValue = params[key] ?? defaults[key];
        const enumOpts = (options ?? {})[key];
        const numValue =
          typeof rawValue === 'number' ? rawValue : Number(rawValue);
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
            {range ? ( // 数值范围型：Slider+InputNumber，字符串安全转数字
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
                  value={isNaN(numValue) ? range.min : numValue}
                  disabled={envKey}
                  style={{ width: settingsControl.sliderWidth }}
                  onChange={(v) => onChange(key, v)}
                />
                <InputNumber
                  min={range.min}
                  max={range.max}
                  value={isNaN(numValue) ? range.min : numValue}
                  disabled={envKey}
                  onChange={(v) => onChange(key, v)}
                />
              </span>
            ) : enumOpts ? ( // 枚举型：Select字符串直绑，禁indexOf/[idx]
              <Select
                options={enumOpts.map((v) => ({ label: v, value: v }))}
                value={
                  typeof rawValue === 'string'
                    ? rawValue
                    : String(rawValue ?? '')
                }
                disabled={envKey}
                style={{ minWidth: 120 }}
                onChange={(v) => onChange(key, v)}
              />
            ) : typeof rawValue === 'number' ? ( // 数值型
              <InputNumber
                value={rawValue}
                disabled={envKey}
                onChange={(v) => onChange(key, v)}
              />
            ) : typeof rawValue === 'boolean' ? ( // 布尔型
              <Switch
                checked={rawValue}
                disabled={envKey}
                onChange={(v) => onChange(key, v)}
              />
            ) : rawValue !== null && typeof rawValue === 'object' ? ( // 对象型：textarea(JSON)，禁String(obj)
              <Input.TextArea
                value={JSON.stringify(rawValue ?? null)}
                disabled={envKey}
                autoSize
                onChange={(e) => {
                  try {
                    onChange(key, JSON.parse(e.target.value));
                  } catch {
                    /* 输入中，blur时提示 */
                  }
                }}
                onBlur={(e) => {
                  try {
                    JSON.parse(e.target.value);
                  } catch {
                    onChange(key, defaults[key]);
                  }
                }}
              />
            ) : (
              // 字符串型
              <Input
                value={String(rawValue ?? '')}
                disabled={envKey}
                onChange={(e) => onChange(key, e.target.value)}
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
