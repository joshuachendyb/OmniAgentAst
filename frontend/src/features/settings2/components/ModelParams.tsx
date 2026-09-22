// 编辑历史: 2026-09-20 小强 - 新建：模型参数区（跟随当前模型+范围+[已修改]+[重置为默认]确认内联）
// 2026-09-21 小欧 - P0-4+P0-6+P0-7：色/字号→令牌、滑块宽→settingsControl、标签宽→settingsSpacing（[58] P0-4/P0-6/P0-7）
// 2026-09-21 小欧 - 全文逐章核查：gap 裸数字 → Spacing.MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小强 - 设置页17问题复核修复：env 接管键禁用控件+EnvTag 标识（杜绝改假值/假保存/切走丢失）；
//   行 flexWrap 防窄屏溢出（[设置页UI审计] 问题2/16）
// 2026-09-22 小欧 - [62]P4 3.2(5) ModelParams 五分支渲染：删 `as number` 类型谎言；rawValue 原值判型 +
//   enumOpts→Select 字符串直绑（禁 indexOf/[idx]）；range→Slider+InputNumber 安全转数字(isNaN 回退 range.min)；
//   number→InputNumber；boolean→Switch；object→TextArea(JSON，blur 失败回退默认)；string→Input。
//   Props 加 options?（枚举选项表）/onReset?（对齐调用方 SettingsPage 已透传的 options）。
// 2026-09-22 小欧 - 布局对齐：复用 settingsRowLayout 统一结构（label 固定宽 + 控件 flex:1 自适应）- 小欧-2026-09-22
// 2026-09-22 小欧 - 提交前清理：import 移除 FontSize（布局重构删掉范围提示行后不再使用，lint unused）- 小欧-2026-09-22
// 2026-09-22 小欧 - 修正：删容器 gap、label 加 fontSize/fontWeight 完全对齐 SettingRow 行容器样式；import 补回 FontSize/FontWeight - 小欧-2026-09-22
// 2026-09-22 小欧 - DRY 收口：行容器/label 改复用 settingsRowStyle/settingsLabelStyle 令牌（删 settingsRowLayout/settingsSpacing 内联展开）；移 Colors/FontSize/FontWeight unused import - 小欧-2026-09-22
import React from 'react';
import { Input, InputNumber, Select, Slider, Switch } from 'antd';
import { Spacing } from '@/utils/stepStyles';
import {
  settingsControl,
  settingsRowStyle,
  settingsLabelStyle,
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
        const renderControl = (): React.ReactNode => {
          if (range) {
            return (
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
            );
          }
          if (enumOpts) {
            return (
              <Select
                options={enumOpts.map((v) => ({ label: v, value: v }))}
                value={
                  typeof rawValue === 'string'
                    ? rawValue
                    : String(rawValue ?? '')
                }
                disabled={envKey}
                style={{ width: settingsControl.selectWidth }}
                onChange={(v) => onChange(key, v)}
              />
            );
          }
          if (typeof rawValue === 'number') {
            return (
              <InputNumber
                value={rawValue}
                disabled={envKey}
                style={{ width: settingsControl.inputNumberWidth }}
                onChange={(v) => onChange(key, v)}
              />
            );
          }
          if (typeof rawValue === 'boolean') {
            return (
              <Switch
                checked={rawValue}
                disabled={envKey}
                onChange={(v) => onChange(key, v)}
              />
            );
          }
          if (rawValue !== null && typeof rawValue === 'object') {
            return (
              <Input.TextArea
                value={JSON.stringify(rawValue ?? null)}
                disabled={envKey}
                autoSize
                style={{ width: settingsControl.textareaWidth }}
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
            );
          }
          return (
            <Input
              value={String(rawValue ?? '')}
              disabled={envKey}
              style={{ width: settingsControl.inputWidth }}
              onChange={(e) => onChange(key, e.target.value)}
            />
          );
        };
        return (
          <div key={key} style={settingsRowStyle}>
            <span style={settingsLabelStyle}>
              {key} {envKey && <EnvTag />}
            </span>
            <span style={{ flex: 1 }}>{renderControl()}</span>
            {dirty[key] && <DirtyDot />}
          </div>
        );
      })}
    </div>
  );
};
