// 编辑历史: 2026-09-20 小强 - 新建：单行渲染（控件↔schema.type↔antd；secret 三态/只读复制/env 只读）
// 2026-09-21 小欧/小强 - 复制成功提示走 showSuccess（等剪贴板结果再提示，不假"已复制"）；
//   宽度/间距改 settingsControl、Spacing 令牌；加 data-settings-key 锚点、窄屏换行
// 2026-09-22 小欧 - int/float 加 precision/step/min-max 与范围提示；行与 label 复用 settingsRowStyle 令牌
// 2026-09-23 小欧 - notice 移到输入框上方；新增 url 类型（宽框，textarea 会按行拆 list 破坏逗号契约）
// 2026-09-26 小欧 - secret 的"清空/确定"改走 provider 通道（settings 写路径已显式拒绝 secret），
//   单一写入口避免分叉；空串按 provider 三态当"不修改"，不擦原值
// 2026-09-26 小欧 - 修 3 个真 bug：①写成功后不再 onChange(undefined)（那是置脏不是刷新，会让整组保存
//   失败连累用户其它改动）→ 改走 onRefresh 重新 load；②清空从未真正发出（联合类型把清空意图吃掉，
//   后端判无变更仍返回 ok = 假成功）→ 按后端契约显式发 {clear:true}，writeSecret 收窄为只管非空值；
//   ③空串"确定"改本地收工不发请求（原来后端什么都不改却回 ok）
// 2026-09-27 小欧 - 掩码纯回显：masked 由后端生成，前端不再对字符串取末 4 位（那等于在前端重算掩码）
// 2026-09-27 07:38 小欧 - 修 F2/F11 同源两处：①三处 InputNumber onChange 补 null 守卫（清空回 null
//   会让 validate 判"不能为空"→ saveKeys 提前 return → 整批其它改动全丢），与 ProviderConfig 同款写法；
//   ②值是裸字符串时只判"是否已配置"、不显示任何内容，保住"已配置"标识（否则用户误以为密钥丢失而重输覆盖）
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
// 2026-09-26 小欧 - [72]第六章(6.5): secret 项的清空改走 provider 通道，需 modelApi
import { modelApi } from '@/services/api/model.api';
// 2026-09-26 小欧 - [72]第九章: security.access_token 走 auth 专用通道（settings 通道拒写 secret）
import { authApi } from '@/services/api/settings.api';

/** [72]第六章(6.5) - 小欧 - 2026-09-26: secret 项的 key → 所属 provider 名（非 provider secret 返回空串）。
 *  key 形状为 `ai.{provider}.{field}`（provider 通道按 ai 区域嵌套写，见 settings_registry:152-154），
 *  故取第 2 段即 provider 名。非 `ai.` 前缀的 secret 项（如 [72]第九章的 `security.access_token`）
 *  不走 provider 通道，返回空串。 */
function secretProviderName(key: string): string {
  const parts = key.split('.');
  return parts.length >= 3 && parts[0] === 'ai' ? parts[1] : '';
}

/** [72]第九章 - 小欧 - 2026-09-26: 按 secret 项的 key 分流到各自的**唯一权威写通道**。
 *  - `ai.{provider}.api_key` → provider 通道（modelApi.updateProvider，[72]第三章三态）
 *  - `security.access_token`     → auth 专用通道（authApi.setToken，[72]第九章）
 *  两类 secret 项的写路径**都**被 settings 通用通道显式拒绝（[72]第六章方案 B），
 *  故此处必须按 key 分派，绝不能把 api_token 发到 provider 通道（会打错端点）。
 *
 *  2026-09-26 - 小欧 - [72]三堂会审后修正(签名收敛 + YAGNI): value 收窄为 `string`（必非空），
 *  且**「清空」不再经本函数** —— 清空是"显式写空串"的独立语义，与"设置一个值"挤在一个联合类型里
 *  必然出岔子（已实际出错: clear 意图在类型转换里被吃掉，详见清空按钮处注释）。
 *  现本函数只负责"设置/修改一个非空密钥值"这一件事（SRP），清空按钮直接调
 *  modelApi.updateProvider(name, { clear: true })。
 */
const writeSecret = async (key: string, value: string): Promise<void> => {
  if (key.startsWith('ai.') && key.endsWith('.api_key')) {
    await modelApi.updateProvider(secretProviderName(key), { api_key: value });
    return;
  }
  if (key === 'security.access_token') {
    // [72]第九章: 口令走 auth 专用端点（后端拒空口令，此处传值必非空）
    await authApi.setToken(value);
    return;
  }
  throw new Error(`未登记的 secret 项写通道: ${key}`);
};

interface Props {
  item: SettingSchemaItem;
  value: unknown;
  source: SettingSource;
  dirty: boolean;
  highlight: boolean;
  onChange: (value: unknown) => void;
  /**
   * 重新拉取设置数据（secret 项走专用通道落盘后，用它刷新该行显示）。
   *
   * 2026-09-26 - 小欧 - [72]三堂会审后修正（修一个真 bug）: 原 secret 的「确定」「清空」成功后调
   *   `onChange(undefined)` 注释写"交回上层刷新该行" —— 但 onChange 是 **settings 通用通道的 setter**
   *   (useSettings.setValue)，不是刷新函数。它做的事是: values[group][key]=undefined 且
   *   `baseline[group][key] === undefined` 不成立 → **dirtyKeys[key]=true（把该行标记为脏）**。
   *   后果（用户可感知的功能损坏）: 用户改完 api_key 点"确定"成功 → 该行已脏 → 接着改任意别的设置 →
   *   点"保存本组" → saveGroup 把这个 secret 键一并提交 → 而 secret 项已被 [72]第六章在 settings
   *   写路径**显式拒绝** → **整组保存失败，用户的其它修改全部丢失**。即"改 A 坏 B"。
   *   故 secret 走专用通道后**一律不碰 onChange**，改走本 onRefresh 重新 load()。
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
      // 2026-09-27 - 小欧 - 纯回显：掩码串由后端 mask_secret_value 生成，前端不判断档位、不拼星号、
      //   不对字符串取末 4 位（那等于在前端重算掩码，且会把明文尾巴显示出来）。
      //   值是裸字符串（非 {configured,masked}）时只判"是否已配置"、不显示任何内容：
      //   该形态不该出现（secret 走 provider 通道后由 onRefresh 重拉掩码），但真出现时也要保住
      //   "已配置"标识，否则用户会误以为密钥丢失而重新输入覆盖。
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
              // [72]第六章(6.5) - 小欧 - 2026-09-26: secret 项「确定」(设置新值)同样走 provider 通道。
              //   空串按 provider 通道三态语义处理为"不修改"（后端 skip 不写），不会擦除原值
              //   —— 这正是第三章三态修复的价值：留空不再等于擦除。
              // 2026-09-26 - 小欧 - [72]三堂会审后修正: 空串**不再白白发一次请求**。
              //   原逻辑把空串也当"设置"提交 → provider 通道收到 api_key: undefined → 后端什么都不改
              //   却仍返回 ok，用户看到"成功"实际零变化（假成功），且白白占用一次网络往返。
              //   空串的真实语义是"不改"，那就**本地直接收工**，不发请求。
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
                  showMessage(
                    ErrorType.NETWORK_ERROR,
                    `保存失败：${e instanceof Error ? e.message : String(e)}`
                  );
                });
            }}
          >
            确定
          </Button>
          {/* [72]第六章(6.5) - 小欧 - 2026-09-26: secret 项的「清空」改走各自唯一权威写通道
              （ai.*.api_key → provider 通道；security.access_token → auth 通道），不再经 onChange → settings 通用通道。
              理由（方案 B）：secret 三态只在专用通道实现；[72]第六章已让 settings 写路径对 secret 项
              **显式拒绝**，若此处仍走 settings 通道，用户一点清空就会拿到"该敏感项不支持经 /settings 写入"的报错。
              两类 secret 项的写路径各自保持单一权威，杜绝同一 key 两个写入口产生分叉。 */}
          {/* 2026-09-26 - 小沈(三遍复核) - 修 A07 遗留死代码：上一版用 hidden={...} 隐藏按钮，
              却把 showMessage 警告留在 onClick 里 —— 按钮不渲染，onClick 永不触发，那段代码是纯死代码
              （留着即"看不见的逻辑"，后人误以为点得到）。改为**条件渲染**：不渲染就真不渲染，
              警告文案改挂到 notice 区之外的用户可见入口（本项 notice 已含关闭鉴权的正确路径说明）。 */}
          {item.key !== 'security.access_token' && (
            <Button
              size="small"
              onClick={() => {
                // 清空=擦除已保存密钥，走 provider 通道的 { clear: true } 显式契约
                // （writeSecret 只接受 string 语义，清空意图在类型转换里会被吃掉，见本文件上方注释）。
                void modelApi
                  .updateProvider(secretProviderName(item.key), { clear: true })
                  .then(() => {
                    onRefresh?.();
                    setEditingSecret(false);
                  })
                  .catch((e) => {
                    showMessage(
                      ErrorType.NETWORK_ERROR,
                      `清空失败：${e instanceof Error ? e.message : String(e)}`
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
