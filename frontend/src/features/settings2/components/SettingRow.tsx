// 编辑历史: 2026-09-20 小强 - 新建：单行渲染（控件↔schema.type↔antd；secret 三态/只读复制/env 只读，见 7.4/7.7）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：复制成功提示改走 errorHandler.showSuccess
// 2026-09-21 小欧 - P0-6：控件宽度→settingsControl 令牌（[58] P0-6）
// 2026-09-21 小欧 - 全文逐章核查：gap:8/marginLeft:8 → Spacing.MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - [59]B-10 渲染: source === 'default' 显示 DefaultTag（后端缺省键新语义）;
//   [59]F-1 修复: 只读复制不立即弹成功，await copyTextToClipboard 结果后再提示（剪贴板权限拒绝时不再假"已复制"）
// 2026-09-21 小欧 - [59]F-1 补漏: showSuccess 在上轮 import 整理中被移除、但复制成功分支(line:52)仍引用,
//   补回 import 消除 tsc 未定义引用错误（编辑历史纪律：错误的加同样不对，立即修正）
// 2026-09-21 小强 - 设置页17问题复核修复：根部加 data-settings-key 搜索滚动锚点；
//   窄屏 labelWidth→88、textarea→100%、行 flexWrap（[设置页UI审计] 问题1/16）
// 2026-09-22 小欧 - int/float 输入增强：int 加 precision=0/step=1 强制整数、两者加 min/max 范围约束；
//   控件右侧显示范围提示（int: "0 ~ 2 · 整数"，float: "0 ~ 2"），range 类型不重复显示
// 2026-09-22 小欧 - 控件宽度统一：range/int/float 的 InputNumber 补齐 rangeNumberWidth/inputNumberWidth 令牌 - 小欧-2026-09-22
// 2026-09-22 小欧 - DRY 收口：行容器/label 样式改复用 settingsRowStyle/settingsLabelStyle 令牌（删 SettingsRowLayout 内联展开）；移 FontWeight unused import - 小欧-2026-09-22
import React, { useState } from 'react';
import { Button, Grid, Input, InputNumber, Select, Slider, Switch } from 'antd';
import { FontSize, Colors, Spacing } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';
import {
  settingsSpacing,
  settingsControl,
  settingsRowStyle,
  settingsLabelStyle,
} from '@/theme/settingsTokens';
import type {
  SettingSchemaItem,
  SettingSource,
} from '@/services/api/settings.api';
import { EnvTag, CopyIcon, DirtyDot, DefaultTag } from './icons';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { copyTextToClipboard } from '@/utils/clipboard';

interface Props {
  item: SettingSchemaItem;
  value: unknown;
  source: SettingSource;
  dirty: boolean;
  highlight: boolean;
  onChange: (value: unknown) => void;
}

export const SettingRow: React.FC<Props> = ({
  item,
  value,
  source,
  dirty,
  highlight,
  onChange,
}) => {
  const [editingSecret, setEditingSecret] = useState(false);
  const [secretInput, setSecretInput] = useState('');
  const disabled = item.readonly || source === 'env';
  // 修正(2026-09-21 小强)：窄屏响应式 label/textarea——原 labelWidth 132 固定 + textarea 320 固定，
  // 窄屏横向溢出（[设置页UI审计] 问题16）
  const bp = Grid.useBreakpoint();
  const isNarrow = !bp.md;
  const labelWidth = isNarrow ? 88 : settingsSpacing.labelWidth;

  const renderControl = (): React.ReactNode => {
    if (item.readonly) {
      return (
        <span>
          <span style={{ fontSize: FontSize.CODE }}>{String(value ?? '')}</span>
          <Button
            type="link"
            icon={<CopyIcon />}
            onClick={() => {
              void copyTextToClipboard(String(value ?? '')).then((r) => {
                if (r.ok) showSuccess('已复制');
                else showMessage(ErrorType.WARNING, '复制失败，请手动复制');
              });
            }}
          />
        </span>
      );
    }
    if (item.secret) {
      // 2026-09-21 BUG-B 修复：value 可为明文（保存中/保存后未回读的瞬时态），
      // 原逻辑按 {configured,suffix} 结构取 configured 对字符串取到 undefined -> 误显"未配置"
      const raw = value;
      const isPlain = typeof raw === 'string';
      const configured = isPlain
        ? raw.length > 0
        : !!(raw as { configured?: boolean })?.configured;
      const suffix = isPlain
        ? raw.slice(-4)
        : ((raw as { suffix?: string })?.suffix ?? '');
      if (!editingSecret) {
        return (
          <span>
            {configured ? `已配置 ····${suffix}` : '未配置'}
            <Button
              type="link"
              disabled={source === 'env'}
              onClick={() => {
                setSecretInput('');
                setEditingSecret(true);
              }}
            >
              {configured ? '修改' : '配置'}
            </Button>
          </span>
        );
      }
      return (
        <span style={{ display: 'inline-flex', gap: Spacing.MD }}>
          <Input.Password
            value={secretInput}
            onChange={(e) => setSecretInput(e.target.value)}
            placeholder="留空=保持原值"
            style={{ width: settingsControl.secretWidth }}
          />
          <Button
            type="primary"
            size="small"
            onClick={() => {
              onChange(secretInput);
              setEditingSecret(false);
            }}
          >
            确定
          </Button>
          <Button
            size="small"
            onClick={() => {
              onChange({ clear: true });
              setEditingSecret(false);
            }}
          >
            清空
          </Button>
          <Button size="small" onClick={() => setEditingSecret(false)}>
            取消
          </Button>
        </span>
      );
    }
    switch (item.type) {
      case 'bool':
        return (
          <Switch
            checked={value as boolean}
            disabled={disabled}
            onChange={onChange}
          />
        );
      case 'select':
        return (
          <Select
            value={value as string}
            disabled={disabled}
            style={{ width: settingsControl.selectWidth }}
            onChange={onChange}
          >
            {(item.options ?? []).map((o) => (
              <Select.Option key={String(o)} value={o as string}>
                {String(o)}
              </Select.Option>
            ))}
          </Select>
        );
      case 'range':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: Spacing.MD,
            }}
          >
            <Slider
              min={item.range?.[0]}
              max={item.range?.[1]}
              step={item.step ?? 1}
              value={value as number}
              disabled={disabled}
              style={{ width: settingsControl.sliderWidth }}
              onChange={onChange}
            />
            <InputNumber
              min={item.range?.[0]}
              max={item.range?.[1]}
              step={item.step ?? 1}
              value={value as number}
              disabled={disabled}
              style={{ width: settingsControl.rangeNumberWidth }}
              onChange={(v) => onChange(v)}
            />
          </span>
        );
      case 'int':
        return (
          <InputNumber
            value={value as number}
            disabled={disabled}
            min={item.range?.[0]}
            max={item.range?.[1]}
            step={1}
            precision={0}
            style={{ width: settingsControl.inputNumberWidth }}
            onChange={(v) => onChange(v)}
          />
        );
      case 'float':
        return (
          <InputNumber
            value={value as number}
            disabled={disabled}
            min={item.range?.[0]}
            max={item.range?.[1]}
            style={{ width: settingsControl.inputNumberWidth }}
            onChange={(v) => onChange(v)}
          />
        );
      case 'textarea':
        return (
          <Input.TextArea
            value={value as string}
            disabled={disabled}
            rows={3}
            style={{
              width: isNarrow ? '100%' : settingsControl.textareaWidth,
            }}
            onChange={(e) => onChange(e.target.value)}
          />
        );
      case 'model_ref':
        return (
          <span style={{ color: Colors.TEXT.SECONDARY }}>
            由模型 Tab 选择器管理
          </span>
        );
      default:
        return (
          <Input
            value={value as string}
            disabled={disabled}
            style={{ width: settingsControl.inputWidth }}
            onChange={(e) => onChange(e.target.value)}
          />
        );
    }
  };

  return (
    <div
      // 修正(2026-09-21 小强)：data-settings-key 作为搜索跳转滚动锚点（[设置页UI审计] 问题1）
      data-settings-key={item.key}
      style={{
        ...settingsRowStyle,
        background: highlight ? chatTokens.colorPrimaryBg : undefined,
        transition: 'background 0.3s',
      }}
    >
      <span
        style={{
          ...settingsLabelStyle,
          width: labelWidth,
        }}
      >
        {item.label}
      </span>
      <span style={{ flex: 1 }}>{renderControl()}</span>
      {item.range && item.type !== 'range' && (
        <span
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.TERTIARY,
            marginLeft: Spacing.SM,
          }}
        >
          {item.range[0]} ~ {item.range[1]}
          {item.type === 'int' && ' · 整数'}
        </span>
      )}
      {dirty && <DirtyDot />}
      {source === 'env' && <EnvTag />}
      {source === 'default' && <DefaultTag />}
      <span
        style={{
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
          marginLeft: Spacing.MD,
        }}
      >
        {/* 调整(2026-09-21 小强)：说明在前生效方式在后——如「同时运行的沙箱并发数，超出排队等待 // 即时生效」 */}
        {item.notice && `${item.notice} // `}
        {item.restart ? '重启生效' : '即时生效'}
      </span>
    </div>
  );
};
