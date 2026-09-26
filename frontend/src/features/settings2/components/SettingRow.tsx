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
// 2026-09-23 小欧 - notice 说明文字移到输入框上方（flexDirection:column）；删除 // 拼接，notice 与即时生效分离 - 小欧-2026-09-23
// 2026-09-23 小欧 - 新增 url 类型：单行 Input 走 baseUrlWidth(360px)，与 ProviderConfig base_url 同款宽框；
//   用于 network.cors_origins（textarea 会按行拆 list 破坏逗号契约，text 默认 180px 太短）- 小欧-2026-09-23
// 2026-09-26 小欧 - [72]第六章(6.5) 落地: secret 项的「清空」与「确定」均改走 **provider 通道**
//   （modelApi.updateProvider），不再经 onChange → settings 通用通道。
//   动机: secret 三态只在 provider 通道实现（model_service.update_provider_config 为唯一权威），
//   而 [72]第六章已让 settings 写路径对 secret 项**显式拒绝**——若前端仍走 settings 通道，
//   用户一点清空/确定就会拿到"该敏感项不支持经 /settings 写入"的报错，功能不可用。
//   两通道 key 语义保持单一权威，杜绝同一 key 两个写入口产生分叉（DRY + 禁止 backward）。
//   配套: 新增 secretProviderName(key) 从 registry key(`ai.{provider}.{field}`)取 provider 名，
//   避免为此新增 prop 改动全部调用方（KISS-DIRECT）；「确定」的空串经 provider 三态处理为"不修改"，
//   不会擦除原值（第三章三态修复的价值）。 — 小欧-2026-09-26
// 2026-09-26 (三堂会审后修正) - 小欧 - 10 大规范 + 关联逻辑复核，本文件 4 处已改：
//   ①[功能 bug · 改A坏B] secret 写成功后调 `onChange(undefined)`，注释却称"刷新该行"——它不是刷新：
//     onChange 是 settings 通道 setter（useSettings.setValue），会 values[key]=undefined 且因 baseline
//     不等而 **dirtyKeys[key]=true**。用户改完密钥点"确定"→ 该行已脏 → 接着改别的设置 → 点"保存本组"
//     → saveGroup 把这个 secret 键一并提交 → 而 secret 已被 [72]第六章在 settings 写路径**显式拒绝**
//     → **整组保存失败、用户的其它修改全丢**。改法: secret 走专用通道后一律不碰 onChange，
//     新增 onRefresh 回调走 load() 重新拉取（SettingsGroup/SettingsPage 已串通）。
//   ②[功能 bug · 静默无操作] 「清空」按钮原走 `writeSecret(key, {clear:true})`，而 writeSecret 的
//     provider 分支只从 value 里取 api_key（value 是对象 → undefined），**clear=true 从未被发出**；
//     后端收到不含 clear 的 patch → 判定无变更 → 返回 ok。前端 .then 照跑、提示成功，
//     **密钥根本没被清空**。根因: 用一个联合类型把"设置值/清空"挤在一起，清空意图在转换里被吃掉。
//     修法: 清空不再经 writeSecret，直接按后端契约 ProviderConfigUpdate.clear 显式发 {clear:true}；
//     writeSecret 签名收窄为 (key, value: string)，只管"设置一个非空值"（SRP）。
//   ③[YAGNI 死代码 + 假成功] 「确定」按钮原把空串也当设置提交 → provider 通道收到 api_key: undefined，
//     后端什么都不改却返回 ok（假成功），还白占一次网络往返。改为空串本地直接收工、不发请求。
//   ④[DRY] writeSecret 两分支内 `typeof value === 'string' ? ... : ...` 兜底随 ②③ 一并删除
//     —— 那两个兜底分支在旧调用方式下永不可达（属"为死分支写代码"）。
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
// 2026-09-26 小欧 - [72]第九章: security.api_token 走 auth 专用通道（settings 通道拒写 secret）
import { authApi } from '@/services/api/settings.api';

/** [72]第六章(6.5) - 小欧 - 2026-09-26: secret 项的 key → 所属 provider 名（非 provider secret 返回空串）。
 *  key 形状为 `ai.{provider}.{field}`（provider 通道按 ai 区域嵌套写，见 settings_registry:152-154），
 *  故取第 2 段即 provider 名。非 `ai.` 前缀的 secret 项（如 [72]第九章的 `security.api_token`）
 *  不走 provider 通道，返回空串。 */
function secretProviderName(key: string): string {
  const parts = key.split('.');
  return parts.length >= 3 && parts[0] === 'ai' ? parts[1] : '';
}

/** [72]第九章 - 小欧 - 2026-09-26: 按 secret 项的 key 分流到各自的**唯一权威写通道**。
 *  - `ai.{provider}.api_key` → provider 通道（modelApi.updateProvider，[72]第三章三态）
 *  - `security.api_token`     → auth 专用通道（authApi.setToken，[72]第九章）
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
  if (key === 'security.api_token') {
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
              （ai.*.api_key → provider 通道；security.api_token → auth 通道），不再经 onChange → settings 通用通道。
              理由（方案 B）：secret 三态只在专用通道实现；[72]第六章已让 settings 写路径对 secret 项
              **显式拒绝**，若此处仍走 settings 通道，用户一点清空就会拿到"该敏感项不支持经 /settings 写入"的报错。
              两类 secret 项的写路径各自保持单一权威，杜绝同一 key 两个写入口产生分叉。 */}
          <Button
            size="small"
            onClick={() => {
              // [72]第九章: 访问口令**不提供"清空=关闭鉴权"** —— 那是部署级危险操作
              //   （一关全站失守），后端 auth/token 亦显式拒绝空口令（防静默关闭）。
              //   故此处前置拦截并给出准确指引，而非让用户点了才报错。
              if (item.key === 'security.api_token') {
                showMessage(
                  ErrorType.WARNING,
                  '访问口令不能清空（清空=关闭鉴权，全站会失去保护）。如需关闭请在后端设环境变量 OMNIAGENT_REQUIRE_AUTH=0'
                );
                return;
              }
              // 2026-09-26 - 小欧 - [72]三堂会审后修正（修一个真功能 bug:「清空」按钮点了没反应）:
              //   原实现 `writeSecret(key, { clear: true })`，而 writeSecret 的 provider 分支写的是
              //   `updateProvider(name, { api_key: value 是不是非空字符串 ? value : undefined })` ——
              //   value 是对象 → 走 undefined 分支 → **clear=true 从未被发出**，后端收到一个不含 clear 的
              //   patch，判定为"无字段变更"→ 原样返回 ok。前端 .then 照跑、提示成功，**密钥根本没被清空**。
              //   这类"静默无操作还报成功"最难查：后端日志正常、前端无报错、用户以为清掉了。
              //   根因是 writeSecret 用一个联合类型把"设置值/清空"两种语义挤在一起，
              //   清空意图在类型转换里被吃掉。修法: 清空不再经 writeSecret，直接按后端契约
              //   ProviderConfigUpdate.clear 显式发 { clear: true }（该字段与 api_key 同级、互斥）。
              void modelApi
                .updateProvider(secretProviderName(item.key), { clear: true })
                .then(() => {
                  onRefresh?.(); // 重新 load（不再走 onChange，理由见 Props.onRefresh 注释）
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
