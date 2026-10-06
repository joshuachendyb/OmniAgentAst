// 编辑历史: 2026-09-24 小欧 - 新建：模型库 Tab（拉取 Provider 远程模型 + 勾选替换式写入
//   ai.{provider}.models；三项过滤 D4/守卫第5条前端对应/脏态不进 SaveBar）- 小欧-2026-09-24
// 2026-09-25 00:05:02 小欧 - 核查修复 4 处：①Modal.confirm title 加粗+content 次级色
//   （复用 SettingsPage 重置确认同款）；②获取按钮去 type=primary 改默认 Button 对齐
//   ModelSelector「添加模型」；③「当前」Tag 去 color=blue 改默认 Tag；④切换 Provider 勾选
//   重置为新 Provider 已配置集（原清空空集，与设计字面不符）- 小欧-2026-09-25
// 2026-09-25 01:13:09 小欧 - Step8 核查修复：过滤「仅看免费」Checkbox 说明字补
//   FontSize.SECONDARY（设计字面要求，原用 antd 默认 14px 主字号）- 小欧-2026-09-25
// 2026-09-25 04:38:28 小健 - 模型列表全链路排序：finalList 落盘前整体按 id 字母序（不分大小写），
//   后端 _parse_remote_models_body 已单点排序，preserve 保留项并入后整体排序保证 YAML/下拉一致 - 小健-2026-09-25
// 2026-09-25 05:05:08 小健 - UI布局调整：①获取 + ②过滤两功能项并排一行（组内标题在上、控件在下），
//   fetchError Alert 与统计行下沉至行外（北京老陈要求）- 小健-2026-09-25
// 2026-09-25 05:11:13 小健 - UI布局调整：「保存所选」按钮移至③列表标题同行、行内水平垂直居中，
//   原右下角独立按钮容器移除（北京老陈要求）- 小健-2026-09-25
// 2026-09-29 小欧 - 列表改 Table + 5 项筛选：后端改为下发模型元数据(价格/上下文/能力/模态)，
//   前端原靠 id.includes('-free') 猜免费，实测 OpenRouter 460 个命中 0，该复选框恒空 - 小欧-2026-09-29
// 2026-09-29 小欧 - 删归属、状态两列：owned_by 实测 OpenRouter 460/460 为 null、另两家全同值，
//   零区分度；「状态」与 Checkbox 的 checked+disabled 重复，改为内联 id 旁 Tag - 小欧-2026-09-29
// 2026-09-29 小欧 - 修 5 处漏洞：env 接管仍可保存(后端必 400)、当前全局模型被踢出提交集、
//   未拉取即误置灰筛选、远端下线项使弹窗数字对不上、关键词搜 description 致命中不可解释 - 小欧-2026-09-29
// 2026-10-03 小欧 - 免费判定迁至 utils/modelUtils；判据扩为三判据 OR，「仅看免费」可筛性改看 freeAvail — 小欧 2026-10-03
// 2026-10-03 小欧 - 「获取模型列表」后增「添加 Provider」按钮（复用同一弹窗/回调，组件不持弹窗状态）— 小欧 2026-10-03
// 2026-10-05 22:16:38 小欧 - 表格增「输出上限」列并排在「上下文」之前（后端随厂商适配新增该字段，
//   北京老陈指令）：两者量级常差 8~16 倍（SenseNova glm-5.2 输出 131072 / 上下文 1048576），
//   并排且输出在前，读表顺序即"先看能吐多少"；复用 formatContext 不另立格式化函数(DRY)。
//   readModalities 改读 input_modalities —— 后端已把厂商两种层级（SenseNova 顶层 / OpenRouter 嵌
//   architecture）归一到该字段，原读 architecture 会让 SenseNova 恒显示"–" — 小欧 2026-10-05
import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Empty,
  Input,
  Modal,
  Select,
  Skeleton,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  CloudDownloadOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
// 2026-09-29 小欧 - 删 settingsRowStyle: 列表改 Table 后已无行容器，import 成了死引用(ESLint 报 unused)
import { settingsControl, settingsModalWidth } from '@/theme/settingsTokens';
import { modelApi } from '@/services/api/model.api';
import type {
  ProviderEntry,
  RemoteModelItem,
  RemoteModelsResponse,
} from '@/services/api/model.api';
import { showSuccess } from '@/services/error/handler';
import { SectionTitle } from './SectionTitle';
// 2026-10-03 小欧 - 免费判定自 utils/modelUtils 导入（组件内零重定义，与单测同源）— 小欧 2026-10-03
import { isFreeModel } from '../utils/modelUtils';

interface Props {
  providers: ProviderEntry[];
  onSaved: (mtime: number) => Promise<void>;
  // 2026-10-03 小欧 - 「添加 Provider」入口：复用 ModelSelector 同一回调与同一弹窗，
  //   本组件不持弹窗状态、不重复实现表单（SLAP/DRY）— 小欧 2026-10-03
  onAddProvider: () => void;
}

// 2026-09-29 小欧 - 筛选/判定的词表与判据全部来自 OpenRouter 460 模型实勘(非臆造取值) — 小欧-2026-09-29
/** 输入模态筛选项：text 实测 460/460 全覆盖(筛它恒等于全集，无区分度)故不设项，
 *  只留 image(292)/file(182)/video(85)/audio(44)。组内 OR、组间 AND。 */
const MODALITY_FILTERS = [
  { label: '图片', value: 'image' },
  { label: '文件', value: 'file' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
];

/** 模态值→中文，供表格 Tag 展示；未收录值原样显示(远端加新模态不必改前端即不至于空白) */
const MODALITY_LABEL: Record<string, string> = {
  text: '文本',
  image: '图片',
  file: '文件',
  video: '视频',
  audio: '音频',
};

/** 智能体能力筛选项：真实函数能力走 supported_features（后端厂商适配新增）。
 *  OpenRouter 写法 tools/structured_outputs/reasoning，SenseNova 写法 tools/json_mode/reasoning
 *  —— 同一语义两个名，本表做 canonical value → 厂商别名 的映射(DRY，两处判定共用)。 */
const FEATURE_FILTERS = [
  { label: '工具调用', value: 'tools' },
  { label: '结构化输出', value: 'structured_outputs' },
  { label: '推理', value: 'reasoning' },
];
// canonical → 厂商别名集（同一语义，各厂商命名不一）：结构化输出 = structured_outputs / json_mode
const FEATURE_ALIASES: Record<string, string[]> = {
  tools: ['tools'],
  structured_outputs: ['structured_outputs', 'json_mode'],
  reasoning: ['reasoning'],
};
const hasFeature = (m: RemoteModelItem, canonical: string): boolean =>
  (FEATURE_ALIASES[canonical] ?? [canonical]).some((alias) =>
    (m.supported_features ?? []).includes(alias)
  );

/** 最小上下文阈值：实测 460 个全有值(min 4095 / max 2,000,000)，<32K 仅 16 个、<128K 43 个，筛有区分度 */
const CONTEXT_OPTIONS = [
  { label: '不限', value: 0 },
  { label: '≥ 32K', value: 32_768 },
  { label: '≥ 128K', value: 131_072 },
  { label: '≥ 200K', value: 200_000 },
  { label: '≥ 1M', value: 1_000_000 },
];

/** 每百万 token 报价：远端是每 token 字符串(0.0000008 → $0.80/M)，按百万量级才可读。
 *  **本函数不判"免费"**：免费是"三判据 OR"的整体语义，只由 isFreeModel 判一次（小欧 2026-10-03 修订）。
 *  若这里也对 0 返回"免费"，会出现 prompt>0 而 completion=0 的模型被显示成"免费"（误报）。 */
const pricePerMillion = (v: string | undefined): string => {
  if (v == null || v === '') return '–';
  const perM = Number(v) * 1_000_000;
  if (!Number.isFinite(perM)) return '–';
  if (perM >= 1) return `$${perM.toFixed(2)}`;
  if (perM >= 0.01) return `$${perM.toFixed(3)}`;
  return `$${perM.toPrecision(2)}`;
};

const formatContext = (n: number | null | undefined): string => {
  if (typeof n !== 'number' || !Number.isFinite(n) || n <= 0) return '–';
  if (n >= 1_000_000) return `${Number((n / 1_000_000).toFixed(1))}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
};

/** 远端模态数组收窄：后端已把厂商两种层级（顶层 / architecture 嵌套）归一到 input_modalities，
 *  此处只读归一后的字段并用 Array.isArray 收窄 — 小欧 2026-10-05 */
const readModalities = (m: RemoteModelItem): string[] => {
  const v = m.input_modalities;
  return Array.isArray(v)
    ? v.filter((x): x is string => typeof x === 'string')
    : [];
};

interface LibraryFilters {
  keyword: string;
  freeOnly: boolean;
  modalities: string[];
  features: string[];
  minContext: number;
}

/** 筛选判据收口一处：组内 OR(任一命中)、组间 AND(全部满足) — 小欧-2026-09-29
 *  关键词只搜表格可见列(id/name): 搜 description 全文会让 the/best 命中两百个模型，
 *  而命中理由收在 Tooltip 里，用户无法解释结果。 */
const matchFilters = (m: RemoteModelItem, f: LibraryFilters): boolean => {
  if (f.freeOnly && !isFreeModel(m)) return false;
  // 未上报 context_length 的按 0 处理：无法证实其达标，故不纳入阈值命中
  if (f.minContext > 0 && (m.context_length ?? 0) < f.minContext) return false;
  if (f.modalities.length > 0) {
    const inputs = readModalities(m);
    if (!f.modalities.some((v) => inputs.includes(v))) return false;
  }
  if (f.features.length > 0) {
    // 2026-10-05 22:16:38 小欧 - 能力判定源由 supported_parameters 切到 supported_features：
    //   前者只含 temperature/stop（采样参数，和"工具/结构化/推理"无关），勾上恒 0 命中；
    //   后者才是模型真能力值，经 hasFeature 按 FEATURE_ALIASES 认厂商别名(structured_outputs≈json_mode)。
    if (!f.features.some((v) => hasFeature(m, v))) return false;
  }
  const kw = f.keyword.trim().toLowerCase();
  if (kw) {
    // 与表格可见列严格同源：模型(id/name)。owned_by 已随「归属」列删除(实勘零区分度)，
    // 若仍搜它就会命中用户看不见的字段 —— 正是漏洞5 要消除的那种不可解释命中。
    const hay = `${m.id} ${m.name ?? ''}`;
    if (!hay.toLowerCase().includes(kw)) return false;
  }
  return true;
};

const TAG_STYLE = { marginRight: Spacing.XS, marginBottom: 2 };
const { Text } = Typography;

/** 元数据缺失项的展示名：Alert 与 Tooltip 共用一处词表 — 小欧 2026-09-29 */
type MetaKey = 'pricing' | 'modality' | 'capability' | 'context';
const MISSING_LABEL: Record<MetaKey, string> = {
  pricing: 'pricing（免费判定）',
  modality: 'architecture.input_modalities（模态）',
  capability: 'supported_features（能力）',
  context: 'context_length（上下文）',
};

export const ModelLibraryTab: React.FC<Props> = ({
  providers,
  onSaved,
  onAddProvider,
}) => {
  const [selectedProvider, setSelectedProvider] = useState<string>(
    providers[0]?.name ?? ''
  );
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [remote, setRemote] = useState<RemoteModelsResponse | null>(null);
  const [filters, setFilters] = useState<LibraryFilters>({
    keyword: '',
    freeOnly: false,
    modalities: [],
    features: [],
    minContext: 0,
  });
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  // 2026-09-24 小欧 - v1.7 DRY：切换/失效守卫共用的选中态重置收口 — 小欧-2026-09-24
  // 2026-09-25 小欧：勾选重置为目标 Provider 已配置集（原空集与设计字面不符）— 小欧-2026-09-25
  // 2026-09-29 小欧：筛选态一并重置（换 Provider 后沿用旧模态/能力条件会筛出空列表）— 小欧-2026-09-29
  const resetSelection = (providerName: string) => {
    const p = providers.find((x) => x.name === providerName);
    setRemote(null);
    setChecked(new Set((p?.models ?? []).map((m) => m.name)));
    setFilters({
      keyword: '',
      freeOnly: false,
      modalities: [],
      features: [],
      minContext: 0,
    });
    setFetchError(null);
  };

  // 设计要求：providers 变化（设置页增删/外部改 yaml）时本地 selectedProvider 失效守卫
  useEffect(() => {
    if (providers.length === 0) return;
    if (!providers.some((p) => p.name === selectedProvider)) {
      setSelectedProvider(providers[0].name);
      resetSelection(providers[0].name);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providers, selectedProvider]);

  const provider = providers.find((p) => p.name === selectedProvider);
  const apiBaseEmpty = provider ? !provider.api_base : true;
  // env 接管只读: 后端 replace_provider_models 对其直接 400，拉取却是读操作不拦，
  // 不拦就是让用户拉得到、勾得了、存不进。对齐 ProviderConfig 的 isEnv 口径 — 小欧 2026-09-29
  const isEnv = provider?.env === true;

  // 元数据可用性按筛选器独立判定: qnaigc 81 项全有 context_length 却无 pricing，
  // 单一开关会因"有上下文"而全开，另三类照样筛出空结果。remote 为 null 返回 null 而非全 false，
  // 否则未拉取就四路置灰，用户会误以为该 provider 不支持 — 小欧 2026-09-29
  const metaAvail = useMemo<Record<MetaKey, boolean> | null>(() => {
    if (!remote?.ok) return null;
    const models = remote.models;
    return {
      pricing: models.some((m) => Object.keys(m.pricing ?? {}).length > 0),
      modality: models.some((m) => readModalities(m).length > 0),
      // 2026-10-05 22:16:38 小欧 - capability 可用性改以 supported_features 为据（能力的真源）。
      capability: models.some((m) => (m.supported_features ?? []).length > 0),
      context: models.some((m) => (m.context_length ?? 0) > 0),
    };
  }, [remote]);
  // 筛选器禁用判据：metaAvail 为 null(未拉取)时不禁用 —— 无数据不等于不支持
  const metaBlocked = (k: MetaKey): boolean => metaAvail?.[k] === false;
  const missingMeta: MetaKey[] = metaAvail
    ? (Object.keys(metaAvail) as MetaKey[]).filter((k) => !metaAvail[k])
    : [];

  // 免费判据已扩为三判据（free 字段/名称尾巴），不再只依赖 pricing，故可筛性改看 freeAvail：
  // 原 metaBlocked('pricing') 会让「无 pricing 但满屏 -free」的 provider（本仓 alpha/beta）永远勾不上。
  const freeAvail = remote?.ok ? remote.models.length > 0 : null;

  // D4 过滤叠加：关键词 + 免费 + 输入模态 + 智能体能力 + 最小上下文（判据收口 matchFilters）
  // 2026-09-29 小欧 - 不加防抖: 漏洞5 根因是 description 千字进 hay，移除后每次按键开销
  //   为 460×(三短串拼接+includes) 亚毫秒级，为此新建 useDebouncedValue 属 YAGNI(KISS-DIRECT)
  const filtered = useMemo(
    () =>
      remote?.ok ? remote.models.filter((m) => matchFilters(m, filters)) : [],
    [remote, filters]
  );

  const filterCount =
    (filters.freeOnly ? 1 : 0) +
    filters.modalities.length +
    filters.features.length +
    (filters.minContext > 0 ? 1 : 0) +
    (filters.keyword.trim() ? 1 : 0);

  const { configuredGroup, unconfiguredGroup } = useMemo(() => {
    const configuredSet = new Set(remote?.configured ?? []);
    const configured: typeof filtered = [];
    const unconfigured: typeof filtered = [];
    for (const m of filtered) {
      (configuredSet.has(m.id) ? configured : unconfigured).push(m);
    }
    return { configuredGroup: configured, unconfiguredGroup: unconfigured };
  }, [filtered, remote]);

  // 远端已下线但配置保留的模型: 无条件并入 finalList(防静默丢配置)，但它们不在
  // remote.models 里故不渲染成行 —— 用户核对不出 finalList.length 的构成。单点算出，
  // 统计行与保存弹窗报出 — 小欧 2026-09-29
  const preservedIds = useMemo(() => {
    if (!remote?.ok) return [];
    const listed = new Set(remote.models.map((m) => m.id));
    return remote.configured.filter(
      (id) => !listed.has(id) && id !== remote.current_model
    );
  }, [remote]);

  // D2 替换式：勾选集 = 最终列表；远端未回但配置里仍有的模型自动保留（防静默丢配置）
  // 当前全局模型无条件保留: 后端守卫会拒「移除当前全局模型」，而表格里的 disabled 只管 UI 手感、
  // 管不到这里的提交集。两道兜底缺一不可: 在远端列表里靠 id===cur，已下线则靠末尾 ids.add — 小欧 2026-09-29
  const finalList = useMemo(() => {
    if (!remote?.ok) return [];
    const cur = remote.current_model;
    const ids = new Set([
      ...remote.models
        .map((m) => m.id)
        .filter((id) => checked.has(id) || id === cur),
      ...preservedIds,
    ]);
    // 当前全局模型既不在远端列表、也不在 configured 时仍须保它，否则后端守卫必拒
    if (cur) ids.add(cur);
    // 2026-09-25 04:38:28 小健 - 全链路字母序: checked 部分继承远端已排序序, preserve 保留项并入后整体排序
    return [...ids].sort((a, b) =>
      a.toLowerCase().localeCompare(b.toLowerCase())
    );
  }, [remote, checked, preservedIds]);

  const removedCount = useMemo(
    () =>
      remote?.ok
        ? remote.configured.filter((id) => !finalList.includes(id)).length
        : 0,
    [remote, finalList]
  );

  const onSelectProvider = (name: string) => {
    setSelectedProvider(name);
    resetSelection(name);
  };

  const fetchList = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await modelApi.fetchRemoteModels(selectedProvider);
      if (!res.ok) {
        setRemote(null);
        setChecked(new Set());
        setFetchError(res.message ?? '拉取失败');
        return;
      }
      setRemote(res);
      setChecked(new Set(res.configured));
    } catch {
      // 400/404 已由 client 拦截器 handleApiError 统一提示，此处只重置
      setRemote(null);
      setChecked(new Set());
    } finally {
      setLoading(false);
    }
  };

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSave = () => {
    if (!remote?.ok || finalList.length === 0) return;
    Modal.confirm({
      // 2026-09-25 小欧 - 5.4.2：title 加粗 PRIMARY、content 次级色（复用 SettingsPage 重置确认同款）— 小欧-2026-09-25
      title: (
        <span
          style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
        >
          替换模型列表
        </span>
      ),
      width: settingsModalWidth.confirm,
      content: (
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          将替换该 Provider 的模型列表为已勾选的 {finalList.length} 个（移除{' '}
          {removedCount} 个）
          {/* 2026-09-29 小欧 - 漏洞4: 隐形保留项单列说明，否则用户核对不出 finalList.length 的构成 */}
          {preservedIds.length > 0 &&
            `；其中 ${preservedIds.length} 个远端已下线但配置保留：${preservedIds.join('、')}`}
        </span>
      ),
      onOk: async () => {
        setSaving(true);
        try {
          // 2026-10-05 22:16:38 小欧 - 保存时把每个勾选模型的「上下文/输入模态」一并上送持久化
          //   （北京老陈指令）；远端已下线保留项只送 id（元数据 unknown，不伪造）。
          const saveModels = finalList.map((id) => {
            const m = remote?.models.find((x) => x.id === id);
            return m
              ? {
                  id,
                  context_length: m.context_length ?? undefined,
                  input_modalities: m.input_modalities ?? [],
                }
              : { id };
          });
          const res = await modelApi.replaceModels(
            selectedProvider,
            saveModels
          );
          showSuccess(
            `已保存：新增 ${res.added.length} 个、移除 ${res.removed.length} 个`
          );
          await onSaved(res.mtime);
          setRemote({ ...remote, configured: finalList });
        } catch {
          // 失败已由 client 拦截器提示，弹窗保留可重试
        } finally {
          setSaving(false);
        }
      },
    });
  };

  // 列表改 Table: 单行放不下 上下文/报价/能力/模态 四类元数据。沿用全库唯一 Table 用法
  // (TrustPanel.tsx) 的 JSX 子元素式。仍分「已配置/未配置」两表: 合并成一张靠列排序会退化掉分组 — 小欧 2026-09-29
  const renderTable = (rows: typeof filtered) => (
    <Table
      dataSource={rows}
      size="small"
      rowKey={(r) => r.id}
      pagination={{ pageSize: 20, size: 'small', showSizeChanger: true }}
      locale={{ emptyText: <Empty description="无匹配模型" /> }}
    >
      <Table.Column
        title="选择"
        width={52}
        render={(_, m: RemoteModelItem) => {
          const isCurrent = remote?.current_model === m.id;
          return (
            <Checkbox
              checked={isCurrent || checked.has(m.id)}
              // 2026-09-29 小欧 - 漏洞1: env 接管只读，勾选无意义(保存必 400)，整列置灰
              disabled={isCurrent || isEnv}
              onChange={() => toggle(m.id)}
            />
          );
        }}
      />
      <Table.Column
        title="模型"
        render={(_, m: RemoteModelItem) => {
          // 只显 id, 名称/描述收进 Tooltip: 原三行布局撑高 3 倍，460 行滚动时视觉噪音压过 id，
          // 而写进 config.yaml 的就是它。描述截 300 字(远端可达上千字) — 小欧 2026-09-29
          const name = m.name && m.name !== m.id ? m.name : '';
          const desc = m.description ?? '';
          const clipped = desc.length > 300 ? `${desc.slice(0, 300)}…` : desc;
          const detail = [name, clipped].filter(Boolean).join('\n');
          // 「当前」内联到 id 旁, 删掉独立「状态」列: 该列与 Checkbox 的 checked+disabled
          // 是同一事实两处渲染(改 A 漏 B 的面)，且 id 才是选型要盯的字段 — 小欧 2026-09-29
          const idCell = (
            <span style={{ fontSize: FontSize.PRIMARY }}>
              {m.id}
              {remote?.current_model === m.id && (
                <Tag style={TAG_STYLE}>当前</Tag>
              )}
            </span>
          );
          return detail ? (
            <Tooltip
              // pre-line: detail 用 \n 拼行，Tooltip 默认单行渲染会把换行压成空格
              title={<span style={{ whiteSpace: 'pre-line' }}>{detail}</span>}
              mouseEnterDelay={0.4}
            >
              {idCell}
            </Tooltip>
          ) : (
            idCell
          );
        }}
      />
      {/* 2026-10-05 22:16:38 小欧 - 增补「输出上限」列并排在「上下文」之前：两者量级常差
       *  8~16 倍（SenseNova 实测 glm-5.2 输出 131072 / 上下文 1048576），并排且输出在前，
       *  读表顺序即"先看能吐多少再看能吃多少"。复用 formatContext，不另立格式化函数(DRY)。 */}
      <Table.Column
        title="输出上限"
        dataIndex="max_output_length"
        width={88}
        align="right"
        sorter={(a: RemoteModelItem, b: RemoteModelItem) =>
          (a.max_output_length ?? 0) - (b.max_output_length ?? 0)
        }
        render={(n: number | null | undefined) => (
          <span style={{ fontSize: FontSize.SECONDARY }}>
            {formatContext(n)}
          </span>
        )}
      />
      <Table.Column
        title="上下文窗口"
        dataIndex="context_length"
        width={88}
        align="right"
        sorter={(a: RemoteModelItem, b: RemoteModelItem) =>
          (a.context_length ?? 0) - (b.context_length ?? 0)
        }
        render={(n: number | null | undefined) => (
          <span style={{ fontSize: FontSize.SECONDARY }}>
            {formatContext(n)}
          </span>
        )}
      />
      <Table.Column
        // 列头必须自带单位: 单位删掉、或塞进 Tooltip 都等于默认不可见(用户不看悬停就不知道
        // $1.50 是什么单位)。列头是常驻标签，单位只能在那儿，故取紧凑写法避折行 — 小欧 2026-09-29
        title="输出价 ($/M)"
        width={112}
        render={(_, m: RemoteModelItem) =>
          isFreeModel(m) ? (
            <Tag color="green">免费</Tag>
          ) : (
            // 只显输出价(远端 pricing 有 6 个子键，全铺开撑爆列宽)；输入价收 Tooltip — 小欧 2026-09-29
            <Tooltip
              title={`输入 ${pricePerMillion(m.pricing?.prompt)} / 百万 token`}
              mouseEnterDelay={0.4}
            >
              <span
                style={{ fontSize: FontSize.SECONDARY, whiteSpace: 'nowrap' }}
              >
                {pricePerMillion(m.pricing?.completion)}
              </span>
            </Tooltip>
          )
        }
      />
      <Table.Column
        title="能力"
        width={168}
        render={(_, m: RemoteModelItem) => {
          // 2026-10-05 22:16:38 小欧 - 能力列由 supported_parameters（采样参数 temperature/stop）
          //   切到 supported_features（模型真能力 tools/json_mode/reasoning），经 hasFeature 认厂商别名。
          const tags = FEATURE_FILTERS.filter((f) => hasFeature(m, f.value));
          return tags.length > 0 ? (
            <>
              {tags.map((t) => (
                <Tag key={t.value} style={TAG_STYLE}>
                  {t.label}
                </Tag>
              ))}
            </>
          ) : (
            <span
              style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.WEAK }}
            >
              –
            </span>
          );
        }}
      />
      <Table.Column
        title="输入模态"
        width={156}
        render={(_, m: RemoteModelItem) => {
          // 无 input_modalities 依据却断言支持文本输入是猜测，无据时显示 – — 小欧 2026-09-29
          const inputs = readModalities(m);
          if (inputs.length === 0) {
            return (
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.WEAK,
                }}
              >
                –
              </span>
            );
          }
          const rest = inputs.filter((v) => v !== 'text' && v !== 'image');
          return (
            <>
              {inputs.includes('text') && <Tag style={TAG_STYLE}>文本</Tag>}
              {inputs.includes('image') && <Tag style={TAG_STYLE}>图片</Tag>}
              {rest.map((v) => (
                <Tag key={v} style={TAG_STYLE}>
                  {MODALITY_LABEL[v] ?? v}
                </Tag>
              ))}
            </>
          );
        }}
      />
      {/* 2026-09-29 小欧 - 删「归属」「状态」两列(北京老陈指令，经实勘确认无价值):
           归属: owned_by 实测 OpenRouter 460/460 为 null(整列显示 –)、qnaigc 81 个全为 system、
             agnes 11 个全为 custom —— 三个 provider 零区分度，纯占 110px。
             同理关键词搜索也去掉 owned_by(漏洞5 已定"只搜表格可见列"，删列后必须同步，否则搜不可见字段)。
           状态: 与 Checkbox 的 checked+disabled 表达同一事实(改 A 漏 B 的重复渲染面)，
             已内联为模型 id 旁的「当前」Tag，信息就近且省 72px。 */}
    </Table>
  );

  const renderGroup = (title: string, rows: typeof filtered) =>
    rows.length > 0 && (
      <div>
        <div
          style={{
            fontSize: FontSize.PRIMARY,
            fontWeight: FontWeight.BOLD,
            margin: `${Spacing.SM}px 0`,
          }}
        >
          {title}（{rows.length}）
        </div>
        {renderTable(rows)}
      </div>
    );

  return (
    <div>
      {/* 2026-09-25 05:05:08 小健 - UI布局: ①获取+②过滤并排一行(北京老陈要求), 组内标题在上控件在下, Alert/统计行下沉行外 - 小健-2026-09-25 */}
      <div
        style={{
          display: 'flex',
          gap: Spacing.XL,
          alignItems: 'flex-start',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <SectionTitle title="── ① 获取 ──" />
          <div
            style={{ display: 'flex', gap: Spacing.MD, alignItems: 'center' }}
          >
            <Select
              value={selectedProvider}
              // 2026-10-05 22:16:38 小欧 - 位置① provider 下拉与位置② 模型名搜索框同宽（北京老陈指令）：
              //   ② 用 filterSearchWidth=160。因 modelSelectWidth=180 为全宽令牌、其它页在用，本页
              //   直接复用 filterSearchWidth，①② 齐平且不动其它页面。
              style={{ width: settingsControl.filterSearchWidth }}
              onChange={onSelectProvider}
              options={providers.map((p) => ({
                value: p.name,
                label: p.label || p.name,
              }))}
            />
            <Button
              icon={<CloudDownloadOutlined />}
              loading={loading}
              disabled={apiBaseEmpty}
              onClick={() => void fetchList()}
            >
              获取模型列表
            </Button>
            {/* 2026-10-03 小欧 - 「添加 Provider」紧邻获取按钮：拉模型前常需先建 Provider，
                放此处省去切回模型 Tab。与 ModelSelector 同款默认 Button + PlusOutlined。 */}
            <Button icon={<PlusOutlined />} onClick={onAddProvider}>
              添加 Provider
            </Button>
            {apiBaseEmpty && (
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.WEAK,
                }}
              >
                未配置 api_base，请先到模型 Tab → ③ Provider 配置填写
              </span>
            )}
            {/* 2026-09-29 小欧 - 漏洞1: env 接管只读，拉取可用但勾选/保存必 400，故明说 */}
            {isEnv && !apiBaseEmpty && (
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.WEAK,
                }}
              >
                该 Provider 的 api_key
                由环境变量接管，模型列表只读（可拉取查看，不可勾选保存）
              </span>
            )}
          </div>
        </div>
        <div>
          <SectionTitle title="── ② 过滤 ──" />
          {/* 2026-09-29 小欧 - 筛选器由「搜索 + 仅看免费」两项扩到五项(北京老陈指令)。
              词表全部来自 OpenRouter 460 模型实勘，见文件头 MODALITY/FEATURE_FILTERS 注释。 */}
          <div
            style={{
              display: 'flex',
              gap: Spacing.MD,
              alignItems: 'center',
              // 2026-10-05 22:16:38 小欧 - 北京老陈指令：位置1过滤行尽量在一行不折行。
              //   nowrap 强制单行；极窄场景靠 overflowX 横滑兜底，杜绝 flexWrap:'wrap' 撑出第二行。
              flexWrap: 'nowrap',
              overflowX: 'auto',
            }}
          >
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="模型名"
              value={filters.keyword}
              onChange={(e) =>
                setFilters((f) => ({ ...f, keyword: e.target.value }))
              }
              style={{ width: settingsControl.filterSearchWidth }}
            />
            <Tooltip title="远端标记免费 / 模型名带 -free 或 :free / 报价输入输出同时为 0">
              <Checkbox
                checked={filters.freeOnly}
                disabled={!freeAvail}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, freeOnly: e.target.checked }))
                }
                style={{ fontSize: FontSize.SECONDARY }}
              >
                仅看免费
              </Checkbox>
            </Tooltip>
            <Tooltip
              title={
                metaBlocked('modality')
                  ? '该 Provider 未返回 architecture.input_modalities，无法按模态筛选'
                  : '可接受的输入模态（组内任一命中即可）'
              }
            >
              <Checkbox.Group
                value={filters.modalities}
                options={MODALITY_FILTERS}
                disabled={metaBlocked('modality')}
                onChange={(v) =>
                  setFilters((f) => ({
                    ...f,
                    modalities: v as string[],
                  }))
                }
              />
            </Tooltip>
            <Tooltip
              title={
                metaBlocked('capability')
                  ? '该 Provider 未返回 supported_features，无法按能力筛选'
                  : '智能体能力（组内任一命中即可）'
              }
            >
              <Checkbox.Group
                value={filters.features}
                options={FEATURE_FILTERS}
                disabled={metaBlocked('capability')}
                onChange={(v) =>
                  setFilters((f) => ({ ...f, features: v as string[] }))
                }
              />
            </Tooltip>
            <Tooltip
              title={
                metaBlocked('context')
                  ? '该 Provider 未返回 context_length，无法按上下文筛选'
                  : '按上下文窗口下限过滤'
              }
            >
              <Select
                value={filters.minContext}
                options={CONTEXT_OPTIONS}
                disabled={metaBlocked('context')}
                onChange={(v) => setFilters((f) => ({ ...f, minContext: v }))}
                // 2026-10-05 22:16:38 小欧 - 位置1尽量一行不折行：上下文下拉由 modelSelectWidth(180)
                //   砍为 contextSelectWidth(96)。北京老陈指令。
                style={{ width: settingsControl.contextSelectWidth }}
              />
            </Tooltip>
            {filterCount > 0 && (
              <Button
                size="small"
                onClick={() =>
                  setFilters({
                    keyword: '',
                    freeOnly: false,
                    modalities: [],
                    features: [],
                    minContext: 0,
                  })
                }
              >
                清空筛选（{filterCount}）
              </Button>
            )}
          </div>
        </div>
      </div>
      {remote?.ok && missingMeta.length > 0 && (
        <Alert
          style={{ marginTop: Spacing.MD }}
          type="info"
          showIcon
          message="该 Provider 部分模型元数据缺失"
          description={`已拉取 ${remote.models.length} 个模型，对方 /models 未返回 ${missingMeta.map((k) => MISSING_LABEL[k]).join('、')}，对应列与筛选已置灰；其余筛选不受影响。`}
        />
      )}
      {fetchError && (
        <Alert
          style={{ marginTop: Spacing.MD }}
          type="error"
          showIcon
          message={fetchError}
        />
      )}
      {remote?.ok && (
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginTop: Spacing.XS,
          }}
        >
          共 {remote.models.length} 个模型
          {filterCount > 0 ? `，命中 ${filtered.length} 个` : ''}
          ，已配置 {remote.configured.length} 个，已勾选 {finalList.length} 个
          {/* 2026-09-29 小欧 - 漏洞4: 保留项不渲染成行(远端无此模型)，此处补数避免与表格对不上 */}
          {preservedIds.length > 0 &&
            `（含 ${preservedIds.length} 个远端已下线保留项）`}
        </div>
      )}

      {/* 2026-09-25 05:11:13 小健 - UI布局: 保存所选按钮移至③列表标题同行并水平垂直居中(北京老陈要求), 原右下角容器移除 - 小健-2026-09-25 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          position: 'relative',
        }}
      >
        <SectionTitle title="── ③ 列表 ──" />
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        >
          <Button
            type="primary"
            // 2026-09-29 小欧 - 漏洞1: env 接管只读，禁用保存(后端 replace_provider_models 直接 400)
            disabled={isEnv || !remote?.ok || finalList.length === 0}
            loading={saving}
            onClick={onSave}
          >
            保存所选（{finalList.length}）
          </Button>
        </div>
      </div>
      {/* 2026-10-05 22:16:38 小欧 - 保存口径提醒：取消勾选某模型 = 该模型已配参数一并清空
          （replace_provider_models 差集孤儿清理：model_params/model_meta 置 None 删块），仅做「隐藏」
          会丢参数。独立一行小字置按钮行下方，贴右对齐，北京老陈要求在保存处明示。 */}
      <Text
        type="secondary"
        style={{
          fontSize: FontSize.TERTIARY,
          display: 'block',
          textAlign: 'right',
        }}
      >
        取消勾选某模型会清空其已配置参数
      </Text>
      {loading && <Skeleton active paragraph={{ rows: 4 }} />}
      {!loading && !remote && (
        <Empty description="点击「获取模型列表」拉取该 Provider 远程模型" />
      )}
      {!loading && remote?.ok && (
        <>
          {renderGroup('已配置', configuredGroup)}
          {renderGroup('未配置 · 待挑选', unconfiguredGroup)}
          {configuredGroup.length === 0 && unconfiguredGroup.length === 0 && (
            <Empty description="无匹配模型" />
          )}
        </>
      )}
    </div>
  );
};
