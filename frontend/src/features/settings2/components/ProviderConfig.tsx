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
// 2026-09-24 小欧 - 保存按钮上移（北京老陈选定方案B）：从表单底部挪到③区首行右侧（标题下第一行右对齐），
//   与 ③ Provider 配置 区标题同行视觉对齐；doSave/表单 state 不动（按钮仍属本组件，KISS 最小改动）- 小欧-2026-09-24
// 2026-09-24 小欧 - 标题行合一（北京老陈反馈两行难看）：SectionTitle 从 SettingsPage 收进本组件，
//   标题+保存按钮同一行三列 grid（标题左|按钮居中|右空列），对齐②参数区标题行风格；env 接管分支同步带标题无按钮 - 小欧-2026-09-24
// 2026-09-24 小欧 - 再修（北京老陈截图复核：grid 实渲染仍两行）：改 flex 强制同行——左1fr+按钮+右1fr，
//   按钮物理居中；SectionTitle 收掉自带上下 margin 并入本行（margin 会撑高行框造成视觉断裂）- 小欧-2026-09-24
// 2026-09-26 - 小欧 - [72]第一章+第八章(8.5-2/8.5-3)：①api_key 落盘前 trim，与同函数 base_url 写法统一
//   （修前只有 base_url 去空格，是遗漏而非设计）；②base_url 留空语义反转为"错误状态"：Colors.ERROR
//   红字 + 保存按钮 disabled，与后端 update_provider_config 的 400 形成前后端双闸；③config.api_key
//   同步改三键恒定（与 model.api.ts ProviderEntry 同一契约）。
// 2026-09-26 - 小欧 - [72]第十章(10.3)：加"测试连接"按钮（与保存并列但语义不同——只读探测，走
//   modelApi.testConnection 不走 onSave；base_url 为空同样禁用）。结果按后端 category 分档文案
//   （设计 10.5 要求"不得统一显示失败"）：ok / key_invalid(401,403) / endpoint_unsupported
//   (404,405,501，该 Provider 无 /models 端点、**不代表 key 无效**) / network_error。
//   传输入框里的 key 实现"保存前验证"（后端仅存内存用于本次 header，不落盘不进日志不回传）。
// 2026-09-26 - 小欧 - [72]第十二章(12.4/12.5)：关 AntD 自带眼睛（坑1 双眼睛冲突：原生眼睛只能显示
//   "刚输入的字符"、看不到已保存的 key，与"看已保存明文"并存会让用户无法分辨），改自定义眼睛 +
//   二次确认(Modal.confirm「将显示明文密钥，请勿截图或分享」) + 30 秒自动恢复打码 + 卸载清理定时器；
//   明文只在内存 state（不写 localStorage）、明文态 readOnly 且 onChange 直接 return；env 接管时不显示。
// 2026-09-26 (三堂会审后修正) - 小欧 - ①YAGNI 删 doSave 开头 `if (baseUrl.trim()==='') return;`
//   （按钮已 disabled，该 return 永不可达，且与本次自己写的注释矛盾）；②DRY 测试文案表提为模块级
//   TEST_RESULT_TEXT；③修 `map[r.category]` 未知分类显示 undefined 的坑，补 `?? network_error` 兜底。
// 2026-09-26 (三堂会审后修正·二) - 小欧 - [SRP] 明文查看 + 测试连接内联使本组件膨胀到 500 行、
//   兼三职，已抽出 SecretRevealInput（12.5）/ TestConnectionProbe（10.3），父组件只留配置表单本责。
// 2026-09-26 (三堂会审后修正·三) - 小欧 - 删本文件残留的 TEST_RESULT_TEXT 常量（已随测试连接迁出，
//   留着即死代码、eslint 报警）——"文案随职责走"，拆分后不在原处留副本。
// 2026-09-26 (掩码契约同步) - 小欧 - 后端 mask_secret_value 按北京老陈裁定改两档（len<8 返
//   prefix="****"，原为 ""），故上方第⑤条"prefix 为空只显示末4位"的旧分档不再成立（只改注释）。
// 2026-09-27 小欧 - ③区字段改后底部保存栏亮起（北京老陈需求）：加可选 onDraftChange（不传=零影响）；
//   新增 buildDiff 取"变更键"集合（只含改过的键，改回原值即变空=自动撤销脏）；本地表单 state 不动。
// 2026-09-27 (三堂会审第6遍修正) 小欧 - 推翻上条的"JSON 签名本地去重"初版：签名与 hook 侧
//   providerDraft 会失真不同步（保存成功时 hook 单方面清草稿）→ 请求在飞期间新输入不再上报、静默丢脏。
//   改为每渲染如实上报，循环防护收口到 setProviderDraft 的等价去重单点。
// 2026-09-27 小欧 - 保存按钮状态化（北京老陈拍板「无修改时灰白不可点，与底部一致」）：无修改=白灰
//   +disabled、有修改=蓝色+「（N 项）」（N=diff 键数，与底栏同源）；判据与上报同源，故保存成功回灰、
//   失败保持蓝可重试，闭环自动正确。
// 2026-09-27 (三堂会审 P0 修复) 小欧 - doSave 提交源统一为 buildDiff()：原 doSave 自带第二套判定，
//   6 字段里 5 个与草稿口径不一致（label 清空会静默丢改动、等值字段白写并 bump mtime），已删除。

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
// 2026-09-26 - 小欧 - [72]三堂会审后修正(SRP 拆分): 原先在此 import modelApi 供内联的"测试连接"使用，
//   该功能已迁到 TestConnectionProbe 组件内部自持，本组件不再需要 modelApi，故删此 import
//   （留着会变成未使用导入，eslint 报警）。

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
    // [72]第七章(7.3)+第十二章(12.5) - 小欧 - 2026-09-26: 三键恒定 {configured, prefix, suffix}，
    // 与 model.api.ts 的 ProviderEntry.api_key 保持一致（同一契约两处声明，形状必须相同）
    api_key: { configured: boolean; prefix: string; suffix: string };
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

  // 草稿 diff：只含改过的键，值即落盘形态。改回原值即从 diff 消失，父层自动撤销脏计数。
  // 本函数是**唯一提交口径**（组件内保存按钮、底部保存栏、按钮计数三处同源，见 doSave）。
  const buildDiff = useCallback((): Record<string, unknown> => {
    const diff: Record<string, unknown> = {};
    if (apiKey.trim() !== '') diff.api_key = apiKey.trim();
    const nowBase = baseUrl.trim();
    if (nowBase !== (config.base_url || '').trim()) diff.base_url = nowBase;
    const nowLabel = label.trim();
    if (nowLabel !== '' && nowLabel !== (config.label || '').trim())
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

  // 2026-09-26 - 小欧 - [72]SRP 拆分：内联的「明文密钥查看」与「key 连通性探测」已抽出为
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
            仍须能改其它字段（第八章 8.5-3 曾用"当前为空"一票否决，属退化，已修）。— 小欧 2026-09-26 */}
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
        {/* 2026-09-26 小欧 - [72]第十章(10.3) 迁出为 TestConnectionProbe（SRP 拆分）：
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

      {/* api_key —— 2026-09-26 小欧 - [72]第十二章(12.5) 迁出为 SecretRevealInput（SRP 拆分）：
          明文查看的 state/定时器/二次确认全在子组件内，本组件不再持有明文（更安全：
          父组件不持有明文即父组件的其它逻辑永远碰不到它）。env 接管时整块只读，不显示眼睛
          —— 由 isEnv 早退分支处理。
          12.2 目标效果：打码（前4位+星号+末4位）显示在**输入框内**，故传 prefix/suffix
          由子组件拼 maskedDisplay；短 key（len<8）后端按 2026-09-26 裁定给 prefix="****"，
          由子组件渲染为 ****+末4 位（不再插 6 星）。 */}
      <div style={settingsRowStyle}>
        <span style={settingsLabelStyle}>api_key</span>
        <SecretRevealInput
          providerName={name}
          value={apiKey}
          onChange={setApiKey}
          configured={config.api_key.configured}
          prefix={config.api_key.prefix}
          suffix={config.api_key.suffix}
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
      {/* [72]第八章(8.5-2) 小欧 2026-09-26: base_url 空 = 错误状态(红色警示)，原样回显不改写。
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
    </div>
  );
};
