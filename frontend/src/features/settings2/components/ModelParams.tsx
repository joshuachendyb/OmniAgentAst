// 编辑历史: 2026-09-20 小强 - 新建：模型参数区（跟随当前模型+范围+[已修改]+[重置为默认]确认内联）
// 2026-09-21 小欧 - 实施：色/字号→令牌、滑块宽→settingsControl、标签宽→settingsSpacing
// 2026-09-21 小欧 - 全文核查：gap 裸数字 → Spacing.MD 令牌（设计文档 v1.12 铁规）
// 2026-09-21 小强 - 设置页17问题复核修复：env 接管键禁用控件+EnvTag 标识（杜绝改假值/假保存/切走丢失）；
//   行 flexWrap 防窄屏溢出（[设置页UI审计] 问题2/16）
// 2026-09-22 小欧 - 实施 ModelParams 五分支渲染：删 `as number` 类型谎言；rawValue 原值判型 +
//   enumOpts→Select 字符串直绑（禁 indexOf/[idx]）；range→Slider+InputNumber 安全转数字(isNaN 回退 range.min)；
//   number→InputNumber；boolean→Switch；object→TextArea(JSON，blur 失败回退默认)；string→Input。
//   Props 加 options?（枚举选项表）/onReset?（对齐调用方 SettingsPage 已透传的 options）。
// 2026-09-22 小欧 - 布局对齐：复用 settingsRowLayout 统一结构（label 固定宽 + 控件 flex:1 自适应）- 小欧-2026-09-22
// 2026-09-22 小欧 - 提交前清理：import 移除 FontSize（布局重构删掉范围提示行后不再使用，lint unused）- 小欧-2026-09-22
// 2026-09-22 小欧 - 修正：删容器 gap、label 加 fontSize/fontWeight 完全对齐 SettingRow 行容器样式；import 补回 FontSize/FontWeight - 小欧-2026-09-22
// 2026-09-22 小欧 - DRY 收口：行容器/label 改复用 settingsRowStyle/settingsLabelStyle 令牌（删 settingsRowLayout/settingsSpacing 内联展开）；移 Colors/FontSize/FontWeight unused import - 小欧-2026-09-22
// 2026-09-23 小欧 - 实施：遍历改 params⊔defaults 并集（addParam 不注入 defaults，原只遍历 defaults 新键不可见；无新键时并集==defaults 键集零行为变化）- 小欧-2026-09-23
// 2026-09-23 小欧 - 十遍会审：safeNum 单点（原 isNaN 三元在 Slider/InputNumber 各写一次重复）- 小欧-2026-09-23
// 2026-09-24 小欧 - ①参数行尾加「删除参数」× 按钮（A 方案，北京老陈拍板）：env 接管键禁用（后端
//   _raise_if_env_takeover 拒保存）；onDelete 由 SettingsPage 透传 s.removeParam；点即删无确认弹窗 - 小欧-2026-09-24
// 2026-09-24 21:56:36 小欧 - 行根加 data-settings-key={key} 搜索/E2E锚点（对齐 SettingRow；模型参数区原先无锚点，
//   fre2e 用 tuning.llm.temperature 永远 count=0 假跳过）— 小欧-2026-09-24
// 2026-09-24 22:34:33 小欧 - 三堂会审修复：①删未使用 onReset 死 prop（YAGNI，全仓无调用方传参、
//   组件未解构未用）；②加 disabled（保存中 saving 锁定参数行全部控件+×按钮，杜绝保存 await 期间
//   继续编辑致 saveModelGroup 闭包快照错位——成功后 defaults/providers 缓存写旧值且 isDirty 误置 false）；
//   锁态抽 lock 局部变量单点（envKey||disabled），EnvTag 标签仍只认 envKey（保存中不误标环境接管）
//   - 小欧-2026-09-24
// 2026-09-25 05:44:50 小健 - range 取值加内置兜底 PARAM_DEFAULT_RANGES[key]（meta 未存 range 时），
//   统一同为数值参数却有的显示滑块+数字框、有的只出数字框的显示形态（北京老陈选定方案）— 小健-2026-09-25
// 2026-11-01 小欧 - 键名统一：①props `defaults` → `baseline`（已保存参数基线，与调用方 ModelState 同名）；
//   ②参数名 context_limit → context_length（与厂商通用名/后端真源同名）。
//   并集渲染 + `params[key] ?? baseline[key]` 显示兜底不变 —— 厂商声明窗口经 load 通道注入 baseline 后，
//   context_length 行即可见可编辑（原本因基线缺失连行都渲染不出来）- 小欧-2026-11-01
// 2026-11-01 小欧 - 基线补 max_output_length 声明行: 控件只读+标「厂商声明」+不显删除钮(该键非后端解析白名单, 随 extra_body 出网易 400) — 小欧-2026-11-01
// 2026-11-09 小欧 - 两处 InputNumber 补 null 守卫：清空数字框不再写入 null 参数值 — 小欧-2026-11-09
import React from 'react';
import { Button, Input, InputNumber, Select, Slider, Switch } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import {
  settingsControl,
  settingsRowStyle,
  settingsLabelStyle,
} from '@/theme/settingsTokens';
import { isDirty, PARAM_DEFAULT_RANGES } from '../utils/modelUtils';
import { DirtyDot, EnvTag } from './icons';

interface Props {
  params: Record<string, unknown>;
  // 2026-11-01 小欧 - 由 defaults 改名 baseline（已保存参数基线，脏判定/显示兜底双用）- 小欧-2026-11-01
  baseline: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  options?: Record<string, string[]>;
  envOverride: Record<string, boolean>;
  onChange: (key: string, value: unknown) => void;
  // 2026-09-24 小欧 - ①参数行 × 删除（A 方案，点即删无确认）；env 接管键按钮禁用 — 小欧-2026-09-24
  onDelete?: (key: string) => void;
  // 2026-09-24 小欧：保存中 saving 锁定参数行（控件+×按钮 disabled）— 小欧-2026-09-24
  disabled?: boolean;
}

// 2026-11-01 小欧 - 厂商声明只读键(基线注入, 非用户参数): max_output_length 必锁死防随 extra_body 出网 — 小欧-2026-11-01
const isDeclaredOnlyKey = (key: string): boolean => key === 'max_output_length';

export const ModelParams: React.FC<Props> = ({
  params,
  baseline,
  ranges,
  options,
  envOverride,
  onChange,
  onDelete,
  disabled = false,
}) => {
  const dirty = isDirty(params, baseline, envOverride);
  return (
    <div>
      {[...new Set([...Object.keys(baseline), ...Object.keys(params)])].map(
        (key) => {
          // 2026-09-25 05:44:50 小健 - 北京老陈选定前端兜底统一: meta 未存 range 时按参数名取内置默认范围,
          //   杜绝同为 context_length 却「有滑块/纯数字框」两种形态(取决于该模型当初加参数时是否写入 range)— 小健-2026-09-25
          const range = ranges[key] ?? PARAM_DEFAULT_RANGES[key];
          const rawValue = params[key] ?? baseline[key];
          const enumOpts = (options ?? {})[key];
          const numValue =
            typeof rawValue === 'number' ? rawValue : Number(rawValue);
          // 修正(2026-09-21 小强)：env 接管键禁用控件 + EnvTag 标识——
          // 原可编辑但 setParam 写入被 isDirty 排除，静默无效（改假值/保存假成功/切走丢失）([设置页UI审计] 问题2)
          const envKey = envOverride[key];
          // 2026-11-01 小欧 - 声明只读键并入锁集; UI 标签单独识别(不与 env 键混一) — 小欧-2026-11-01
          const declaredOnly = isDeclaredOnlyKey(key);
          // 2026-09-24 小欧：保存中整体锁定（envKey||disabled||declaredOnly 单点；EnvTag 只认 envKey）
          const lock = envKey || declaredOnly || disabled;
          const renderControl = (): React.ReactNode => {
            if (range) {
              const safeNum = isNaN(numValue) ? range.min : numValue;
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
                    value={safeNum}
                    disabled={lock}
                    style={{ width: settingsControl.sliderWidth }}
                    onChange={(v) => onChange(key, v)}
                  />
                  <InputNumber
                    min={range.min}
                    max={range.max}
                    value={safeNum}
                    disabled={lock}
                    onChange={(v) => {
                      // 清空数字框回 null 时不提交：null 会写成参数值并恒判脏
                      if (v !== null) onChange(key, v);
                    }}
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
                  disabled={lock}
                  style={{ width: settingsControl.selectWidth }}
                  onChange={(v) => onChange(key, v)}
                />
              );
            }
            if (typeof rawValue === 'number') {
              return (
                <InputNumber
                  value={rawValue}
                  disabled={lock}
                  style={{ width: settingsControl.inputNumberWidth }}
                  onChange={(v) => {
                    // 清空数字框回 null 时不提交：null 会写成参数值并恒判脏
                    if (v !== null) onChange(key, v);
                  }}
                />
              );
            }
            if (typeof rawValue === 'boolean') {
              return (
                <Switch
                  checked={rawValue}
                  disabled={lock}
                  onChange={(v) => onChange(key, v)}
                />
              );
            }
            if (rawValue !== null && typeof rawValue === 'object') {
              return (
                <Input.TextArea
                  value={JSON.stringify(rawValue ?? null)}
                  disabled={lock}
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
                      onChange(key, baseline[key]);
                    }
                  }}
                />
              );
            }
            return (
              <Input
                value={String(rawValue ?? '')}
                disabled={lock}
                style={{ width: settingsControl.inputWidth }}
                onChange={(e) => onChange(key, e.target.value)}
              />
            );
          };
          return (
            <div key={key} data-settings-key={key} style={settingsRowStyle}>
              <span style={settingsLabelStyle}>
                {key}{' '}
                {declaredOnly && (
                  <span
                    style={{
                      fontSize: FontSize.SECONDARY,
                      color: Colors.TEXT.WEAK,
                    }}
                  >
                    厂商声明
                  </span>
                )}{' '}
                {envKey && <EnvTag />}
              </span>
              <span style={{ flex: 1 }}>{renderControl()}</span>
              {dirty[key] && <DirtyDot />}
              {/* 2026-09-24 小欧 - ①删除参数：行尾 × 图标钮，env 接管禁用；点即删（北京老陈拍板 A 方案）- 小欧-2026-09-24 */}
              {/* 2026-11-01 小欧 - 声明只读键不显删除钮(删了对应 yaml 里什么都没有, 重现造成误导) — 小欧-2026-11-01 */}
              {onDelete && !declaredOnly && (
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={lock}
                  onClick={() => onDelete(key)}
                  aria-label={`删除参数 ${key}`}
                  style={{
                    marginLeft: Spacing.XS,
                    minWidth: 'auto',
                    padding: '0 4px',
                  }}
                />
              )}
            </div>
          );
        }
      )}
    </div>
  );
};
