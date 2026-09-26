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
// 2026-09-26 - 小欧 - [72]第一章(1.3-2) + 第八章(8.5-2)(8.5-3) 落地:
//   (1)第一章 api_key 落盘前 trim(patch.api_key = apiKey.trim())，与同函数 base_url 的 trim 写法统一；
//     修前 base_url 去了空格而 api_key 没有，是遗漏而非设计(同一保存函数内行为分叉)
//   (2)第八章 base_url 留空语义反转: 原文案"留空=清空地址(恢复默认直连)"改为"URL 为空，此 Provider 无法调用(错误状态)"，
//     为空时以 Colors.ERROR 红字显示(base_url 不属密钥，原样回显不做任何改写)
//   (3)第八章 保存按钮在 base_url 为空时 disabled + doSave 入口 return 不提交: 错误状态不可保存，
//     用 disabled 而非静默 return，避免用户点击后"没反应"无提示
//   (4)与后端 model_service.update_provider_config 的 base_url 空 -> 400 形成前后端双闸 - 小欧-2026-09-26
// 2026-09-26 - 小欧 - [72]第十章(10.3) 落地: key 正确性检测（测试连接按钮）
//   ①保存按钮旁加"测试连接"按钮，语义与保存并列但不同 —— 它是只读探测（不改配置），
//     故走 modelApi.testConnection 而非 onSave；base_url 为空时同样禁用（地址不通测了无意义）
//   ②结果按后端返回的 category 分档文案（设计 10.5 明写"不得统一显示失败"）：
//     ok=连接成功 / key_invalid(401,403)=key 无效或无权限 / endpoint_unsupported(404,405,501)=
//     该 Provider 无 /models 端点、key 未验证、**不代表 key 无效** / network_error=请检查 base_url、与 key 无关
//   ③传输入框里的 key 实现"保存前验证"（后端仅存内存用于本次 header，不落盘不进日志）；
//     前端不在此回显 key
//   ④组件内 config.api_key 类型同步改三键恒定（与 model.api.ts ProviderEntry 同一契约两处声明）— 小欧-2026-09-26
// 2026-09-26 - 小欧 - [72]第十二章(12.4/12.5) 落地: 眼睛按钮查看已保存明文（三项已定决策全部实现）
//   ①关 AntD 自带眼睛(visibilityToggle={false}) —— 坑1「双眼睛冲突」: 原生眼睛只能显示"刚输入的字符"
//     (输入框初值恒为 ''，它看不到已保存的 key), 与新增的"看已保存明文"眼睛并存会让用户无法分辨
//   ②自定义眼睛 + 二次确认(Modal.confirm「将显示明文密钥，请勿截图或分享」)，确认后才调
//     modelApi.getApiKeyPlain 取明文
//   ③30 秒自动恢复打码: setTimeout 到期清空明文并恢复打码态; 组件卸载时清理定时器(防内存泄漏 +
//     防卸载后回调 setState); 手动点眼睛关闭时亦立即清除明文
//   ④明文只在内存 state，**不写 localStorage**；明文态输入框 readOnly + onChange 直接 return
//     (避免把明文当新值提交出去)；env 接管时按钮不显示(上方 isEnv 早退分支已覆盖)
//   ⑤打码文案改"前4位 X + 末4位 Y"（prefix 为空时只显示末4位，即 4~7 位短 key 不给 prefix）— 小欧-2026-09-26
// 2026-09-26 (三堂会审后修正) - 小欧 - 10 大规范复核，本文件 3 处已改：
//   ①[YAGNI 死代码] doSave 开头的 `if (baseUrl.trim() === '') return;` 删除 —— 同一改动里保存按钮已
//     disabled={baseUrl.trim() === ''}，按钮禁用时用户点不到，该 return 永不可达；且它与本次自己写的
//     注释直接矛盾（注释写"用 disabled 而非静默 return，避免用户点击后没反应"，代码却是静默 return）。
//     只留 disabled 一处把关：空值的唯一可见表现是"按钮点不动"，不另埋隐形分支。
//   ②[DRY] 测试结果文案表由 doTestConnection 体内提到模块级常量 TEST_RESULT_TEXT —— 原写法每次点击
//     重建同内容对象，且文案埋在业务逻辑里不便与后端 category 一一对账。
//   ③[关联逻辑漏洞] 修 `map[r.category]` 未知分类显示 undefined 的坑：后端新增分类或分类拼错时，
//     界面会显示 "undefined（后端信息: ...）"。补 `?? network_error` 兜底，未知分类按网络/地址问题提示
//     并附后端原文。此为"前端比后端旧"或"分类枚举漂移"时的可见故障，未修等于把内部错误抛给用户。
// 2026-09-26 (三堂会审后修正·二) - 小欧 - [SRP] 明文查看 + 测试连接两块功能内联在本组件，
//   使本组件同时承担"Provider 配置表单 / 明文密钥查看(30秒自动隐藏+二次确认) / key 连通性探测"三件事，
//   组件膨胀到 500 行、任一功能改动都要读完整个组件（违反单一职责）。已把二者各自抽为独立组件：
//     SecretRevealInput（第十二章 12.5 明文查看）
//     TestConnectionProbe（第十章 10.3 测试连接）
//   父组件只留"配置表单"本责，状态与样式令牌按需传入，不新造第二套渲染分支。
//   2026-09-26 (三堂会审后修正·三) - 小欧 - 删本文件残留的 TEST_RESULT_TEXT 文案表常量：
//     它在上一轮已随"测试连接"迁到 TestConnectionProbe 内，此处留着即死代码
//     （eslint no-unused-vars 已实测报出该 warning）。"文案随职责走"是拆分纪律的必然结果：
//     拆分后不许在原处留一份副本，那等于把 DRY 违规从"函数内重建"升级成"跨文件两份"。
//   2026-09-26 (掩码契约同步) - 小欧 - 后端 mask_secret_value 按北京老陈 2026-09-26 裁定改两档，
//     len<8 由返 prefix="" 改返 prefix="****"，故上方第⑤条历史里"prefix 为空只显示末4位"的旧分档
//     已不再成立；本文件 :285 附近活注释同步为新契约（只改注释，逻辑零改动）。
// 2026-09-27 小欧 - ③区字段改后底部保存栏亮起（北京老陈需求「3修改了, 出现保存的按钮」）：
//   ①Props 加可选 onDraftChange（字段 diff 上报回调；不传=单测挂载的独立用法，零影响）；
//   ②新增 buildDiff：本地表单值 vs config 基线的**变更键**集合（与 doSave 提交语义对齐——
//     api_key 非空才算改/base_url trim 后不等才算改/label 留空=保持原值不算改/timeout、max_retries、
//     动态键不等才算改）；只含改过的键，改回原值即变空=自动撤销脏（S6 同款语义）；
//   ③上报 effect 用 JSON 签名去重（config 引用变化会重算，签名相同不通知，防父层 setState 循环）；
//   ④本组件本地表单 state 不动（受控输入/焦点/明文查看逻辑零改动），③自带按钮 onSave 链不变 - 小欧-2026-09-27
// 2026-09-27 (三堂会审第6遍修正) 小欧 - 推翻上条③的初版实现（lastDiffSig 签名去重）：
//   签名缓存与 hook 侧 providerDraft 会失真不同步（保存成功时 hook 单方面清草稿，本地签名仍停在
//   旧值）→ 请求在飞期间的新输入不再上报，静默丢脏。改为每渲染如实上报，循环防护收口到
//   useSettings.setProviderDraft 的等价去重单点（详见 effect 处注释）- 小欧-2026-09-27
// 2026-09-27 小欧 - 保存按钮状态化（北京老陈拍板「无修改时灰白不可点，与底部一致」）：
//   ①原按钮 type="primary" 常年蓝色、无脏态判定——改没改一个样，用户不知道何时该点它；
//   ②改后：无修改=default 白灰+disabled；有修改=primary 蓝色+计数「（N 项）」（N=diff 键数，
//     与底部「保存本组(N 项)」同源同口径）；base_url 原值被清空的错误状态守卫保留仍禁；
//   ③判据与上报同源（buildDiff），保存成功→草稿清空→按钮回灰、保存失败→草稿保留→按钮
//   保持蓝色可重试，闭环自动正确；doSave 提交语义不变（仍送全量表单值）- 小欧-2026-09-27

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
  // 2026-09-27 小欧 - ③区脏计数：保存按钮 灰白(disabled)/蓝+计数 的判据与显示（存数字而非
  //   键数组——相同数字 React setState 会 bail out，天然防渲染循环；数组新引用会循环）- 小欧-2026-09-27
  const [dirtyCount, setDirtyCount] = useState(0);

  const isEnv = config.env === true;

  // 2026-09-27 小欧 - ③区草稿 diff（只含改过的键，值=落盘形态）：
  //   与 doSave 的提交语义对齐（api_key trim 非空、base_url trim 不等、label 非空且不等、
  //   timeout/max_retries/动态键不等）——改回原值 diff 即空，父层自动撤销脏计数（S6 同款）。
  //   doSave 无条件送 timeout/max_retries 是"等值重写"，diff 只送真变更，二者字段值同源无分叉。
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
    // 2026-09-27 小欧 - useCallback 显式依赖（exhaustive-deps）：表单六态 + config 基线，
    //   任一变化才重建引用触发 effect 重报；config 引用变（缓存刷新/内联 fallback）也在此覆盖
    //   （原在 effect 注释里靠"每渲染"覆盖，现由依赖显式表达，语义等价且 lint 干净）- 小欧-2026-09-27
  }, [apiKey, baseUrl, label, timeout, maxRetries, dynamicValues, config]);

  // 2026-09-27 小欧 - diff 上报（底部保存栏亮起数据源）：无依赖数组=任一表单值/基线变化即重算，
  //   每次渲染都如实上报、**不做本地签名去重**——初版用 lastDiffSig 去重，被三堂会审第6遍抓出状态
  //   失真：hook 保存成功会单方面清空 providerDraft，本地签名还停在旧值就不再上报，此时（请求
  //   在飞的几百 ms 内）新改的字段会「输入框有值、草稿无记录、保存栏归零」静默丢脏。改为全量
  //   上报后，防循环唯一防线=useSettings.setProviderDraft 的 JSON 等价去重（同一 diff 重报不改
  //   state 引用、不触发渲染，循环在此终止；DRY：去重只此一处维护）- 小欧-2026-09-27
  useEffect(() => {
    const diff = buildDiff();
    // 2026-09-27 小欧 - 同一份 diff 双出口：本地脏计数（按钮亮/灰）+ 父层草稿（底部保存栏）；
    //   相同数字 setState 被 React bail out，不产生渲染循环。依赖含内联 buildDiff（每渲染新引用
    //   = 每渲染如实上报，与设计一致，同时满足 exhaustive-deps）- 小欧-2026-09-27
    setDirtyCount(Object.keys(diff).length);
    onDraftChange?.(diff);
  }, [buildDiff, onDraftChange]);

  // 2026-09-26 - 小欧 - [72]三堂会审后修正(SRP): 原先内联在本组件的两块功能已各自抽出为独立组件 ——
  //   ①「明文密钥查看(二次确认 + 30 秒自动恢复打码 + 不写 localStorage)」→ SecretRevealInput
  //   ②「key 连通性探测(按 category 分档文案)」→ TestConnectionProbe
  //   本组件回归单一职责：只负责 Provider 配置表单的取值/校验/提交。相关 state、定时器清理、
  //   Modal.confirm、文案表一并随之迁出（拆分只改归属，不改业务行为）。

  const doSave = async () => {
    // [72]第八章(8.5-3) - 小欧 - 2026-09-26 修正: 原此处有 `if (baseUrl.trim() === '') return;`，
    //   与同一改动的按钮 `disabled={baseUrl.trim() === ''}` 重复，且是**死代码**——按钮禁用时用户点不到，
    //   永远走不到这个 return。更糟的是它与本文自己写的注释相矛盾（注释明写"用 disabled 而非静默 return，
    //   避免用户点击后没反应"，代码却正是静默 return）。已删除该 return，只保留按钮 disabled 一处把关：
    //   空值唯一的可达路径是"点了没反应"，那由 disabled 表达，而不是在函数里再埋一个隐形分支。
    //   与 api_key 的"留空=保持原值"方向相反：api_key 允许先建后填，base_url 是必要配置不可为空。
    const patch: Record<string, unknown> = {};
    // [72]第一章(1.3-2) 小欧 2026-09-26: api_key 落盘前 trim，与 base_url 写法统一(此前只有 base_url 去了空格)
    if (apiKey.trim() !== '') patch.api_key = apiKey.trim();
    // 2026-09-26 小欧 - 修"保存按钮被 base_url 一票否决"（[72]第八章改动引入的退化）：
    //   改前无条件 `patch.base_url = baseUrl.trim()`，于是"yaml 里本来就没有 api_base"的 provider
    //   （靠默认地址直连的老配置）会提交空串 → 后端 400；而按钮又被 disabled 死点，
    //   结果**改显示名/超时/重试这类无关字段也存不下去**。
    //   正确语义与 api_key 同向（"留空=保持原值"）：
    //     · 原本就空、现在仍空 → 不进 patch（= 没改这个字段，后端不校验、不会 400）
    //     · 原本有值、现在被清空 → 照送，由后端 400 拦住（"清空 URL"确是错误状态）
    const _origBase = (config.base_url || '').trim();
    const _nowBase = baseUrl.trim();
    if (_nowBase !== '' || _origBase !== '') patch.base_url = _nowBase;
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
        {/* [72]第八章(8.5-3) + 2026-09-26 修正 - 小欧: base_url "为空即错误状态不可保存" 的判据是
          **"原本有值却被清空"**，不是"当前为空"。原本就空（老配置缺 api_base）时按钮必须可用，
          否则改 label/timeout/max_retries 也存不下去（改前用 `baseUrl.trim()===''` 一票否决 = 退化）。
          2026-09-27 小欧 - 状态化（北京老陈拍板「无修改时灰白不可点，与底部一致」）：
          无修改 → default 白灰 + disabled；有修改 → primary 蓝 + 计数「（N 项）」（N=diff 键数，
          与底部「保存本组(N 项)」同源同口径）；base_url 原值清空错误状态守卫叠加保留仍禁。 */}
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
