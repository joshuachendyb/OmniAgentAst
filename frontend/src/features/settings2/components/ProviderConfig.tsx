// 编辑历史: 2026-09-20 小强 - 新建：Provider 配置区（统一表单；写走 PUT /providers 统一链 + mtime 同步，见 7.3.2/8.4.1）
// 2026-09-20 小强 - v4.17 纠错：撤销内嵌 <ProviderSettings shouldLoad />——旧组件自带保存按钮直调旧 /config API，
//   内嵌会造成双真相源 + modelApi.updateProvider 死代码；改为读全局 providerConfig state、保存走 PUT /providers。
// 2026-09-21 小欧 - P2-6：isEnv 时渲染 EnvTag + 警示文案（[58] P2-6）
// 2026-09-21 小欧 - P2-7：清空 api_key 按钮改 danger + 间距分隔（[58] P2-7）
// 2026-09-21 小欧 - V-1：base_url 留空=保持原值，与 api_key 语义对齐（[58] V-1）
// 2026-09-21 小欧 - 重组区块：清空api_key移入操作区，保存按钮限宽（方案C）
// 2026-09-21 小欧 - 补 max_retries：config 类型+表单字段+doSave patch 全链路补齐（后端 update_provider_config 支持 max_retries 键）
// 2026-09-21 小强 - 切 provider 表单值不跟随修复：Form 加 key={name} 重挂刷新（initialValues 只在挂载生效；KISS-DIRECT 一行直解，不加 effect 链条，北京老陈定）
// 2026-09-21 小强 - 修正：内层 key 证伪（rc-field-form 源码：setInitialValues merge(新值,旧仓库)旧赢+默认preserve不清仓，form 实例常驻则重挂无效）；key 上移调用方，删内层冗余 key（北京老陈定）
// 2026-09-21 小强 - 设置页17问题复核修复：base_url 留空=清空（后端支持空串落盘api_base=''）；保存成功复位 api_key
//   防明文残留二次重复提交（失败父级 rethrow 保留输入）；env 接管补解除指引（[设置页UI审计] 问题5/6/14）
// 2026-09-22 小欧 - [62]P6 4.3(6)：label 显示名编辑入口——Props.config 加 label、onSave patch 加 label?、
//   doSave 收集（非空 trim 留空=保持原值）、表单 base_url 后加「显示名」Input（后端 key_map/DTO 早已支持，
//   前端补入口即闭环）；types/useSettings/SettingsPage 三文件同批联动
// 2026-09-22 小欧 - [62]P8 4.3(9)-3-c：①Props.config 加 param_types + [key:string]:unknown 动态索引、
//   onSave patch 加动态索引；②doSave 动态收集循环（param_types 非静态 keys、values[k]!==undefined 送 patch）；
//   ③渲染区加动态字段（param_types 除已硬编码字段外，number→InputNumber/boolean→Switch/string→Input，
//   值回填走 initialValues 天然生效）——rate_limit 等新参数前端零改代码。
// 2026-09-22 小欧 - 控件宽度统一：api_key/base_url 使用 apiKeyWidth/baseUrlWidth(360px)令牌；显示名/timeout/max_retries 使用 inputWidth/inputNumberWidth(240px)令牌
// 2026-09-22 小欧 - 布局重构：去 AntD Form，改 SettingRow 的 flex 行布局 + React state 管理字段值（复用 settingsRowLayout，DRC/SRP/KISS-DIRECT）- 小欧-2026-09-22
// 2026-09-22 小欧 - DRY+令牌收口：EXISTING_KEYS/STATIC_KEYS 重复 Set → HARDCODED_KEYS 单 Set；行容器/label 改复用 settingsRowStyle/settingsLabelStyle（删本地 ROW_STYLE/LABEL_STYLE）；EXTRA_STYLE paddingTop/paddingBottom、保存按钮 padding 裸数字 → Spacing 令牌 - 小欧-2026-09-22
import React, { useState } from 'react';
import { Button, Input, InputNumber, Switch } from 'antd';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import {
  settingsControl,
  settingsSpacing,
  settingsRowStyle,
  settingsLabelStyle,
} from '@/theme/settingsTokens';
import { EnvTag } from './icons';

// 2026-09-22 小欧 - DRY 收口：EXISTING_KEYS/STATIC_KEYS 两 Set 内容完全相同合并为 HARDCODED_KEYS（渲染跳过 + doSave 动态收集共用）
const HARDCODED_KEYS = new Set([
  'api_key',
  'base_url',
  'label',
  'timeout',
  'max_retries',
]);

interface Props {
  name: string;
  config: {
    api_key: { configured: boolean; suffix: string };
    base_url: string;
    label: string;
    timeout: number;
    max_retries: number;
    retry_times?: number;
    env: boolean;
    param_types?: Record<
      string,
      { type: string; label: string; min?: number; default?: unknown }
    >;
    [key: string]: unknown;
  };
  onSave: (patch: {
    api_key?: string;
    base_url?: string;
    label?: string;
    timeout?: number;
    retry_times?: number;
    max_retries?: number;
    clear?: boolean;
    [key: string]: unknown;
  }) => Promise<void>;
}

const EXTRA_STYLE: React.CSSProperties = {
  marginLeft: settingsSpacing.labelWidth,
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.SECONDARY,
  paddingTop: Spacing.XS,
  paddingBottom: Spacing.MD,
};

export const ProviderConfig: React.FC<Props> = ({ name, config, onSave }) => {
  const [saving, setSaving] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(config.base_url ?? '');
  const [label, setLabel] = useState(config.label ?? '');
  const [timeout, setTimeoutVal] = useState(config.timeout ?? 150);
  const [maxRetries, setMaxRetries] = useState(config.max_retries ?? 3);
  const [dynamicValues, setDynamicValues] = useState<Record<string, unknown>>(
    () => {
      const init: Record<string, unknown> = {};
      for (const k of Object.keys(config.param_types ?? {})) {
        if (!HARDCODED_KEYS.has(k) && config[k] !== undefined) {
          init[k] = config[k];
        }
      }
      return init;
    }
  );

  const isEnv = config.env === true;

  const doSave = async () => {
    const patch: Record<string, unknown> = {};
    if (apiKey.trim() !== '') patch.api_key = apiKey;
    patch.base_url = baseUrl.trim();
    if (label.trim() !== '') patch.label = label.trim();
    patch.timeout = timeout;
    patch.max_retries = maxRetries;
    for (const k of Object.keys(config.param_types ?? {})) {
      if (HARDCODED_KEYS.has(k)) continue;
      if (dynamicValues[k] !== undefined) patch[k] = dynamicValues[k];
    }
    setSaving(true);
    try {
      await onSave(patch);
      setApiKey('');
    } catch {
      /* 保存失败：保留输入 */
    } finally {
      setSaving(false);
    }
  };

  if (isEnv)
    return (
      <div>
        <EnvTag />
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          该 Provider 配置被 {name.toUpperCase()}_API_KEY
          环境变量接管，页面只读。如需解除，请删除该环境变量后重启后端。
        </span>
      </div>
    );

  return (
    <div>
      {/* api_key */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>api_key</span>
        <span style={{ flex: 1 }}>
          <Input.Password
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              config.api_key.configured ? '已配置，留空保持原值' : '未配置'
            }
            autoComplete="new-password"
            style={{ width: settingsControl.apiKeyWidth }}
          />
        </span>
      </div>
      <div style={EXTRA_STYLE}>
        {config.api_key.configured
          ? `已配置（末4位 ${config.api_key.suffix}），留空=保持原值`
          : '未配置，留空=保持原值'}
      </div>

      {/* base_url */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>base_url</span>
        <span style={{ flex: 1 }}>
          <Input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            style={{ width: settingsControl.baseUrlWidth }}
          />
        </span>
      </div>
      <div style={EXTRA_STYLE}>留空=清空地址（恢复默认直连）</div>

      {/* 显示名 */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>显示名</span>
        <span style={{ flex: 1 }}>
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            style={{ width: settingsControl.inputWidth }}
          />
        </span>
      </div>
      <div style={EXTRA_STYLE}>Provider 显示名称，留空=保持原值</div>

      {/* timeout */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>timeout</span>
        <span style={{ flex: 1 }}>
          <InputNumber
            min={1}
            value={timeout}
            onChange={(v) => {
              if (v !== null) setTimeoutVal(v);
            }}
            style={{ width: settingsControl.inputNumberWidth }}
          />
        </span>
      </div>

      {/* max_retries */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>max_retries</span>
        <span style={{ flex: 1 }}>
          <InputNumber
            min={0}
            value={maxRetries}
            onChange={(v) => {
              if (v !== null) setMaxRetries(v);
            }}
            style={{ width: settingsControl.inputNumberWidth }}
          />
        </span>
      </div>

      {/* 动态字段 */}
      {Object.entries(config.param_types ?? {}).map(([key, meta]) =>
        HARDCODED_KEYS.has(key) ? null : (
          <div key={key} style={settingsRowStyle}>
            <span style={settingsLabelStyle}>{meta.label}</span>
            <span style={{ flex: 1 }}>
              {meta.type === 'number' ? (
                <InputNumber
                  min={meta.min}
                  value={dynamicValues[key] as number}
                  onChange={(v) =>
                    setDynamicValues((prev) => ({ ...prev, [key]: v }))
                  }
                  style={{ width: settingsControl.inputNumberWidth }}
                />
              ) : meta.type === 'boolean' ? (
                <Switch
                  checked={dynamicValues[key] as boolean}
                  onChange={(v) =>
                    setDynamicValues((prev) => ({ ...prev, [key]: v }))
                  }
                />
              ) : (
                <Input
                  value={String(dynamicValues[key] ?? '')}
                  onChange={(e) =>
                    setDynamicValues((prev) => ({
                      ...prev,
                      [key]: e.target.value,
                    }))
                  }
                  style={{ width: settingsControl.inputWidth }}
                />
              )}
            </span>
          </div>
        )
      )}

      {/* 保存按钮 */}
      <div style={{ padding: `${Spacing.LG}px 0` }}>
        <Button type="primary" onClick={() => void doSave()} loading={saving}>
          保存 Provider 配置（立即生效）
        </Button>
      </div>
    </div>
  );
};
