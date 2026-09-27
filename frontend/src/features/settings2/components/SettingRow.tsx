// 编辑历史: 2026-09-20 小强 - 新建：单行渲染（控件↔schema.type↔antd；secret 三态/只读复制/env 只读）
// 2026-09-21 小欧/小强 - 复制成功提示走 showSuccess（等剪贴板结果再提示）；宽度/间距改 design token
// 2026-09-22 小欧 - int/float 加 precision/step/min-max 与范围提示
// 2026-09-23 小欧 - notice 移到输入框上方；新增 url 类型（宽框，textarea 会按行拆 list）
// 2026-09-26 小欧 - secret 写/清空改走各自专用通道（settings 写路径拒绝 secret）；空串当"不修改"，
//   本地收工不发请求（原会提交 undefined → 后端零改动却回 ok = 假成功）；写成功改走 onRefresh，
//   不碰 onChange（那是通用通道 setter，调用会置脏 → 保存本组时 secret 键被拒 → 整组失败）
// 2026-09-27 小欧 - 掩码纯回显（由后端生成，前端不重算）；InputNumber onChange 补 null 守卫
// 2026-09-27 小欧 - [75]BUG-D/F：两处 catch 改用公用 classifyError（403→AUTH_403，原硬编码
//   NETWORK_ERROR 把"权限不够"说成"网络错误"）+ extractErrorMessage（取后端 detail，
//   原 e.message 是 axios 的英文 "Request failed with status code 4xx"）；writeSecret 去掉
//   自包前缀，错误文案统一在调用处给出
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
import {
  showMessage,
  showSuccess,
  classifyError,
  extractErrorMessage,
  ErrorType,
} from '@/services/error/handler';
import { copyTextToClipboard } from '@/utils/clipboard';
// 2026-09-26 小欧 - [72]第六章(6.5): secret 项的清空改走 provider 通道，需 modelApi
import { modelApi } from '@/services/api/model.api';
// 2026-09-26 小欧 - [72]第九章: security.access_token 走 auth 专用通道（settings 通道拒写 secret）
import { authApi } from '@/services/api/settings.api';

/** secret 项 key → 所属 provider 名；非 ai.* 前缀返回空串（该类走各自专用通道）。
 *  key 形状 ai.{provider}.{field}，取第 2 段。 */
function secretProviderName(key: string): string {
  const parts = key.split('.');
  return parts.length >= 3 && parts[0] === 'ai' ? parts[1] : '';
}

/** 按 secret 项 key 分流到唯一权威写通道（settings 通用通道显式拒绝写 secret，[72]第六章方案 B）。
 *  - ai.{provider}.api_key → modelApi.updateProvider
 *  - security.access_token  → authApi.setToken
 *  value 收窄为非空 string：「清空」是显式 clear 语义，不走本函数（否则 clear 意图会在类型转换中被吃掉）。
 *  错误文案与类型不在此包装，统一由调用处 classifyError + extractErrorMessage 给出（[75]BUG-D）。
 */
/** provider 通道的实际写调用；单测可替换以注入失败（默认走真实实现）。 */
export let providerWrite = (
  provider: string,
  payload: { api_key: string } | { clear: true }
): Promise<unknown> => modelApi.updateProvider(provider, payload);

const writeSecret = async (key: string, value: string): Promise<void> => {
  if (key.startsWith('ai.') && key.endsWith('.api_key')) {
    await providerWrite(secretProviderName(key), { api_key: value });
    return;
  }
  if (key === 'security.access_token') {
    await authApi.setToken(value);
    return;
  }
  throw new Error(`未登记的 secret 项写通道: ${key}`);
};

/** 单测专用：替换 provider 写入口以注入失败；传 undefined 恢复默认。 */
export function __setProviderWrite(
  fn?: (
    p: string,
    payload: { api_key: string } | { clear: true }
  ) => Promise<unknown>
): void {
  providerWrite =
    fn ?? ((provider, payload) => modelApi.updateProvider(provider, payload));
}

interface Props {
  item: SettingSchemaItem;
  value: unknown;
  source: SettingSource;
  dirty: boolean;
  highlight: boolean;
  onChange: (value: unknown) => void;
  /**
   * 重新拉取设置数据（secret 走专用通道落盘后刷新该行显示）。
   *
   * secret 一律不碰 onChange —— 它是 settings 通用通道的 setter，调用会把该行标脏，
   * 随后"保存本组"会把 secret 键一并提交，而 settings 写路径显式拒绝 secret（[72]第六章）
   * → 整组保存失败、用户的其它修改全部丢失。
   */
  onRefresh?: () => void;
}

export const SettingRow: React.FC<Props> = ({
  item,
  value,
  source,
  dirty,
  highlight,
  onChange,
  onRefresh,
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
      // 纯回显：掩码串由后端生成，前端不判断档位、不拼星号、不取末 4 位（等于在前端重算掩码）
      // 值为裸字符串时只判是否已配置、显示为空：保住"已配置"标识，避免用户误以为密钥丢失而重输覆盖
      const cfg =
        typeof value === 'string'
          ? value.length > 0
          : !!(value as { configured?: boolean })?.configured;
      const shown =
        typeof value === 'string'
          ? ''
          : ((value as { masked?: string })?.masked ?? '');
      if (!editingSecret) {
        return (
          <span>
            {cfg ? `已配置 ${shown}` : '未配置'}
            <Button
              type="link"
              disabled={source === 'env'}
              onClick={() => {
                setSecretInput('');
                setEditingSecret(true);
              }}
            >
              {cfg ? '修改' : '配置'}
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
              // secret「确定」走 provider 通道。空串按三态语义当"不修改"（后端 skip 不写），不擦原值
              // 空串本地直接收工、不发请求：原逻辑把它当"设置"提交 → provider 收到 undefined → 后端零改动
              // 却回 ok（假成功），且白占一次往返
              const input = secretInput.trim();
              if (input === '') {
                setSecretInput('');
                setEditingSecret(false);
                return;
              }
              void writeSecret(item.key, input)
                .then(() => {
                  onRefresh?.(); // 重新 load 拉取最新掩码/配置态（不再走 onChange，理由见 Props.onRefresh 注释）
                  setSecretInput('');
                  setEditingSecret(false);
                })
                .catch((e) => {
                  // [75]BUG-D/F：类型与文案统一走公用函数，后端 detail 不再被丢弃
                  showMessage(
                    classifyError(e),
                    extractErrorMessage(e) ?? '保存失败'
                  );
                });
            }}
          >
            确定
          </Button>
          {/* secret 的「清空」走各自专用通道（api_key→provider、access_token→auth），
              理由见 writeSecret docstring。access_token 无「清空」语义：后端拒空口令，
              关闭鉴权走 OMNIAGENT_REQUIRE_AUTH=0（见本项 notice）。 */}
          {item.key !== 'security.access_token' && (
            <Button
              size="small"
              onClick={() => {
                // 清空=擦除已保存密钥，走 provider 通道的 { clear: true } 显式契约
                // （writeSecret 只管非空值，清空意图在类型转换里会被吃掉）
                void modelApi
                  .updateProvider(secretProviderName(item.key), { clear: true })
                  .then(() => {
                    onRefresh?.();
                    setEditingSecret(false);
                  })
                  .catch((e) => {
                    showMessage(
                      classifyError(e),
                      `清空失败：${extractErrorMessage(e) ?? '未知原因'}`
                    );
                  });
              }}
            >
              清空
            </Button>
          )}
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
              onChange={(v) => {
                if (v !== null) onChange(v);
              }}
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
            onChange={(v) => {
              if (v !== null) onChange(v);
            }}
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
            onChange={(v) => {
              if (v !== null) onChange(v);
            }}
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
      case 'url':
        return (
          <Input
            value={value as string}
            disabled={disabled}
            style={{ width: settingsControl.baseUrlWidth }}
            onChange={(e) => onChange(e.target.value)}
          />
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
      <span
        style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}
      >
        {item.notice && (
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {item.notice}
          </span>
        )}
        <span>{renderControl()}</span>
      </span>
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
        {item.restart ? '重启生效' : '即时生效'}
      </span>
    </div>
  );
};
