// 编辑历史: 2026-09-20 小强 - 新建：Provider 配置区（统一表单；写走 PUT /providers 统一链 + mtime 同步，见 7.3.2/8.4.1）
// 2026-09-20 小强 - v4.17 纠错：撤销内嵌 <ProviderSettings shouldLoad />——旧组件自带保存按钮直调旧 /config API，
//   内嵌会造成双真相源 + modelApi.updateProvider 死代码；改为读全局 providerConfig state、保存走 PUT /providers。
// 2026-09-21 小欧 - 实施：isEnv 时渲染 EnvTag + 警示文案
// 2026-09-21 小欧 - 实施：清空 api_key 按钮改 danger + 间距分隔
// 2026-09-21 小欧 - 实施：base_url 留空=保持原值，与 api_key 语义对齐
// 2026-09-21 小欧 - 重组区块：清空api_key移入操作区，保存按钮限宽（方案C）
// 2026-09-21 小欧 - 补 max_retries：config 类型+表单字段+doSave patch 全链路补齐（后端 update_provider_config 支持 max_retries 键）
// 2026-09-21 小强 - 切 provider 表单值不跟随修复：Form 加 key={name} 重挂刷新（initialValues 只在挂载生效；KISS-DIRECT 一行直解，不加 effect 链条，北京老陈定）
// 2026-09-21 小强 - 修正：内层 key 证伪（rc-field-form 源码：setInitialValues merge(新值,旧仓库)旧赢+默认preserve不清仓，form 实例常驻则重挂无效）；key 上移调用方，删内层冗余 key（北京老陈定）
// 2026-09-21 小强 - 设置页17问题复核修复：base_url 留空=清空（后端支持空串落盘api_base=''）；保存成功复位 api_key
//   防明文残留二次重复提交（失败父级 rethrow 保留输入）；env 接管补解除指引（[设置页UI审计] 问题5/6/14）
// 2026-09-22 小欧 - 实施：label 显示名编辑入口——Props.config 加 label、onSave patch 加 label?、
//   doSave 收集（非空 trim 留空=保持原值）、表单 base_url 后加「显示名」Input（后端 key_map/DTO 早已支持，
//   前端补入口即闭环）；types/useSettings/SettingsPage 三文件同批联动
// 2026-09-22 小欧 - 实施：①Props.config 加 param_types + [key:string]:unknown 动态索引、
//   onSave patch 加动态索引；②doSave 动态收集循环（param_types 非静态 keys、values[k]!==undefined 送 patch）；
//   ③渲染区加动态字段（param_types 除已硬编码字段外，number→InputNumber/boolean→Switch/string→Input，
//   值回填走 initialValues 天然生效）——rate_limit 等新参数前端零改代码。
// 2026-09-22 小欧 - 控件宽度统一：api_key/base_url 使用 apiKeyWidth/baseUrlWidth(360px)令牌；显示名/timeout/max_retries 使用 inputWidth/inputNumberWidth(240px)令牌
// 2026-09-22 小欧 - 布局重构：去 AntD Form，改 SettingRow 的 flex 行布局 + React state 管理字段值（复用 settingsRowLayout，DRC/SRP/KISS-DIRECT）- 小欧-2026-09-22
// 2026-09-22 小欧 - DRY+令牌收口：EXISTING_KEYS/STATIC_KEYS 重复 Set → HARDCODED_KEYS 单 Set；行容器/label 改复用 settingsRowStyle/settingsLabelStyle（删本地 ROW_STYLE/LABEL_STYLE）；EXTRA_STYLE paddingTop/paddingBottom、保存按钮 padding 裸数字 → Spacing 令牌 - 小欧-2026-09-22
// 2026-09-24 小欧 - 保存按钮上移（北京老陈选定方案B）：从表单底部挪到③区首行右侧（标题下第一行右对齐），
//   与 ③ Provider 配置 区标题同行视觉对齐；doSave/表单 state 不动（按钮仍属本组件，KISS 最小改动）- 小欧-2026-09-24
// 2026-09-24 小欧 - 标题与保存按钮同行（flex 三列，标题左|按钮居中|右空列）。
// 2026-09-26 小欧 - api_key 落盘前 trim；base_url 留空改判为错误（红字+禁用保存，与后端 400 双闸）。
// 2026-09-26 小欧 - 加"测试连接"（只读探测走 testConnection，不走 onSave）；结果按后端 category 分档文案。
// 2026-09-26 小欧 - 关 AntD 自带眼睛，改自定义眼睛（二次确认+30 秒自动打码+卸载清 timer），明文只存内存。
// 2026-09-26 小欧 - [SRP] 抽出 SecretRevealInput / TestConnectionProbe，本组件只留配置表单本责。
// 2026-09-27 小欧 - 改后亮底部保存栏：buildDiff 取变更键集合（改回原值即自动撤销脏），加可选 onDraftChange。
// 2026-09-27 小欧 - 保存按钮状态化：无修改=灰+disabled，有修改=蓝+「（N 项）」，判据与上报同源。
// 2026-09-27 小欧 - doSave 提交源统一为 buildDiff()，消除第二套口径；动态数字字段 onChange 补 null 守卫；
//   buildDiff 基线改用原值比较，使带空格的历史脏值 api_base 能被清理。
// 2026-09-27 07:38 小欧 - 修 F3/F7：后端 masked 变化即复位本地 api_key。原先只在 doSave 清，而底部保存栏走
//   saveProviderDraft 不经 doSave → 落盘后本地仍留明文、且被 buildDiff 重新算成脏（底栏存不干净）。

import React, { useCallback, useEffect, useState } from 'react';
import { Button, Input, InputNumber, Switch } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { SecretRevealInput } from './SecretRevealInput';
import { TestConnectionProbe } from './TestConnectionProbe';
import {
  settingsControl,
  settingsSpacing,
  settingsRowStyle,
  settingsLabelStyle,
} from '@/theme/settingsTokens';
import { EnvTag } from './icons';
// 2026-09-22 小欧 - DRY：渲染跳过与动态收集共用一份 HARDCODED_KEYS
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
    // 2026-09-27 小欧 - 掩码契约 {configured, masked}（后端一次生成 masked，本组件只原样下传），
    // 与 model.api.ts 的 ProviderEntry.api_key 保持一致（同一契约两处声明，形状必须相同）
    api_key: { configured: boolean; masked: string };
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
  // 2026-09-27 小欧 - ③区字段变更草稿上报（可选：单测独立挂载不传即无副作用）- 小欧-2026-09-27
  onDraftChange?: (diff: Record<string, unknown>) => void;
}

const EXTRA_STYLE: React.CSSProperties = {
  marginLeft: settingsSpacing.labelWidth,
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.SECONDARY,
  paddingTop: Spacing.XS,
  paddingBottom: Spacing.MD,
};

export const ProviderConfig: React.FC<Props> = ({
  name,
  config,
  onSave,
  onDraftChange,
}) => {
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
  // 保存按钮的判据与显示（存数字：相同值 React setState 会 bail out，天然防循环）
  const [dirtyCount, setDirtyCount] = useState(0);

  const isEnv = config.env === true;

  // 2026-09-27 小欧 - 修 F3/F7：后端 masked 变化 = 上次输入已落盘，复位 api_key。
  //   否则底部保存栏（不经 doSave）落盘后本地仍留明文并被 buildDiff 重新算成脏。保存失败时 masked 不变，保留输入。
  useEffect(() => {
    setApiKey('');
  }, [config.api_key.masked]);

  // 草稿 diff：只含改过的键，值即落盘形态。改回原值即从 diff 消失，父层自动撤销脏计数。
  // 本函数是**唯一提交口径**（组件内保存按钮、底部保存栏、按钮计数三处同源，见 doSave）。
  const buildDiff = useCallback((): Record<string, unknown> => {
    const diff: Record<string, unknown> = {};
    if (apiKey.trim() !== '') diff.api_key = apiKey.trim();
    const nowBase = baseUrl.trim();
    // 2026-09-27 - 小欧 - 比较时只 trim 待提交的一边，配置那边用原值。
    // 原因：历史脏数据的 api_base 可能带首尾空格（后端下发时原样透出）。若两边都 trim，
    //       脏值 trim 后与输入值相同 → 判定"没改" → 按钮不亮，脏值永远清不掉。
    if (nowBase !== (config.base_url || '')) diff.base_url = nowBase;
    const nowLabel = label.trim();
    if (nowLabel !== '' && nowLabel !== (config.label || ''))
      diff.label = nowLabel;
    if (timeout !== (config.timeout ?? 150)) diff.timeout = timeout;
    if (maxRetries !== (config.max_retries ?? 3)) diff.max_retries = maxRetries;
    for (const k of Object.keys(config.param_types ?? {})) {
      if (HARDCODED_KEYS.has(k)) continue;
      if (dynamicValues[k] !== undefined && dynamicValues[k] !== config[k])
        diff[k] = dynamicValues[k];
    }
    return diff;
    // 依赖含 config 基线：缓存刷新/内联 fallback 换引用也会重算，等值即空 diff，lint 干净 — 小欧 2026-09-27
  }, [apiKey, baseUrl, label, timeout, maxRetries, dynamicValues, config]);

  // 同一份 diff 双出口：本地脏计数（按钮亮/灰）+ 父层草稿（底部保存栏）。
  // 有意不做本地签名去重：父层保存成功会单方面清空 providerDraft，本地签名会卡在旧值不再上报，
  // 导致"输入框有值、草稿无记录、保存栏归零"静默丢脏。防循环由 setProviderDraft 的 JSON 等价
  // 去重唯一承担（同一 diff 重报返回原 state 引用、不触发渲染，DRY：去重只此一处维护）。— 小欧 2026-09-27
  useEffect(() => {
    const diff = buildDiff();
    setDirtyCount(Object.keys(diff).length);
    onDraftChange?.(diff);
  }, [buildDiff, onDraftChange]);

  // 2026-09-26 - 小欧 - SRP 拆分：内联的「明文密钥查看」与「key 连通性探测」已抽出为
  //   SecretRevealInput / TestConnectionProbe，本组件回归单一职责（配置表单取值/校验/提交）。

  const doSave = async () => {
    // 2026-09-27 - 小欧 - 提交源统一为 buildDiff()（DRY）：原 doSave 自带第二套判定，6 字段里 5 个与
    //   草稿口径不一致 ⇒ 清空 label 时底栏不亮但改动消失、等值字段白写并 bump mtime。统一后与底栏/
    //   按钮计数同一份 diff。不会退化成空提交：按钮按 dirtyCount===0 禁用，saveProviderDraft 另有空守卫。
    const patch = buildDiff();
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
        {/* env 接管只读：标题仍在（搜索锚点），无保存按钮；裸 span 与正常分支同款防两行 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            margin: `${Spacing.LG}px 0 ${Spacing.XS}px`,
          }}
        >
          <span
            style={{
              fontSize: FontSize.PRIMARY,
              fontWeight: FontWeight.BOLD,
            }}
          >
            ── ③ Provider 配置 ──
          </span>
        </div>
        <EnvTag />
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          该 Provider 配置被 {name.toUpperCase()}_API_KEY
          环境变量接管，页面只读。如需解除，请删除该环境变量后重启后端。
        </span>
      </div>
    );

  return (
    <div>
      {/* 2026-09-24 小欧 - 标题+保存按钮强制同一行（北京老陈截图：仍两行+按钮靠右）：
          flex 三段 = 左 spacer 1fr | 按钮 | 右 spacer 1fr → 按钮物理居中；
          标题用裸 span（不用 SectionTitle 的 block+margin，防独占一行） */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          margin: `${Spacing.LG}px 0 ${Spacing.XS}px`,
        }}
      >
        <span
          style={{
            flex: 1,
            fontSize: FontSize.PRIMARY,
            fontWeight: FontWeight.BOLD,
          }}
        >
          ── ③ Provider 配置 ──
        </span>
        {/* 无修改 → 灰白不可点；有修改 → 蓝 + 「（N 项）」（N=diff 键数，与底部保存栏同源）。
            base_url 守卫是"原本有值却被清空"（错误状态），不是"当前为空"——原本就空的老配置
            仍须能改其它字段（设计稿曾用"当前为空"一票否决，属退化，已修）。— 小欧 2026-09-26 */}
        <Button
          type={dirtyCount > 0 ? 'primary' : 'default'}
          onClick={() => void doSave()}
          loading={saving}
          disabled={
            dirtyCount === 0 ||
            (baseUrl.trim() === '' && (config.base_url || '').trim() !== '')
          }
        >
          保存 Provider 配置（立即生效）
          {dirtyCount > 0 ? `（${dirtyCount} 项）` : ''}
        </Button>
        {/* 2026-09-26 小欧 - 迁出为 TestConnectionProbe（SRP 拆分）：
            与保存并列但语义不同 —— 只读探测（不改配置），故不走 onSave。
            base_url 为空时同样禁用（地址不通测了无意义）。 */}
        <TestConnectionProbe
          providerName={name}
          probeKey={apiKey}
          baseUrlReady={baseUrl.trim() !== ''}
          marginLeft={Spacing.SM}
        />
        <span style={{ flex: 1 }} />
      </div>

      {/* api_key —— 明文查看已迁入 SecretRevealInput（父组件不持有明文）；env 接管时整块只读，
          由 isEnv 早退分支处理。打码串由后端生成，本组件只传 masked 原样下传。 */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>api_key</span>
        <SecretRevealInput
          providerName={name}
          value={apiKey}
          onChange={setApiKey}
          configured={config.api_key.configured}
          masked={config.api_key.masked}
          width={settingsControl.apiKeyWidth}
        />
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
      {/* 小欧 2026-09-26: base_url 空 = 错误状态(红色警示)，原样回显不改写。
          红色复用既有语义 token Colors.ERROR(utils/stepStyles.ts:140)，不新造色值。 */}
      <div
        style={{
          ...EXTRA_STYLE,
          color: baseUrl.trim() === '' ? Colors.ERROR : undefined,
        }}
      >
        {baseUrl.trim() === ''
          ? '⚠️ URL 为空，此 Provider 无法调用（错误状态）'
          : 'URL 为 Provider 的必要配置，不能为空'}
      </div>

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
                  onChange={(v) => {
                    // 2026-09-27 - 小欧 - null = 清空 = 不修改（同本文件 timeout/max_retries 静态字段）。
                    // 漏判会把 null 送进 patch、后端原样落盘 ⇒ YAML 出现 `rate_limit: null`。
                    // case: settings2-dynamic-null.test.ts
                    if (v !== null) {
                      setDynamicValues((prev) => ({ ...prev, [key]: v }));
                    }
                  }}
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
    </div>
  );
};
