// 编辑历史: 2026-09-24 小欧 - 新建：[68] 模型库 Tab（拉取 Provider 远程模型 + 勾选替换式写入
//   ai.{provider}.models；三项过滤 D4/守卫第5条前端对应/脏态不进 SaveBar）- 小欧-2026-09-24
// 2026-09-25 00:05:02 小欧 - 第五章核查修复 4 处：①Modal.confirm title 加粗+content 次级色
//   （复用 SettingsPage 重置确认同款）；②获取按钮去 type=primary 改默认 Button 对齐
//   ModelSelector「添加模型」；③「当前」Tag 去 color=blue 改默认 Tag；④切换 Provider 勾选
//   重置为新 Provider 已配置集（原清空空集，与设计 5.2-1 字面不符）- 小欧-2026-09-25
// 2026-09-25 01:13:09 小欧 - 第七章 Step8 核查修复：过滤「仅看免费」Checkbox 说明字补
//   FontSize.SECONDARY（§5.4.2 字面要求，原用 antd 默认 14px 主字号）- 小欧-2026-09-25
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
  Tag,
  Tooltip,
} from 'antd';
import { CloudDownloadOutlined, SearchOutlined } from '@ant-design/icons';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import {
  settingsControl,
  settingsModalWidth,
  settingsRowStyle,
} from '@/theme/settingsTokens';
import { modelApi } from '@/services/api/model.api';
import type {
  ProviderEntry,
  RemoteModelsResponse,
} from '@/services/api/model.api';
import { showSuccess } from '@/services/error/handler';
import { SectionTitle } from './SectionTitle';

interface Props {
  providers: ProviderEntry[];
  onSaved: (mtime: number) => Promise<void>;
}

// D4 免费过滤：名称含 -free 或等于 big-pickle（对齐 scripts 过滤规则）
const isFreeModel = (id: string): boolean =>
  id.includes('-free') || id === 'big-pickle';

export const ModelLibraryTab: React.FC<Props> = ({ providers, onSaved }) => {
  const [selectedProvider, setSelectedProvider] = useState<string>(
    providers[0]?.name ?? ''
  );
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [remote, setRemote] = useState<RemoteModelsResponse | null>(null);
  const [keyword, setKeyword] = useState('');
  const [freeOnly, setFreeOnly] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  // 2026-09-24 小欧 - [68] v1.7 DRY：切换/失效守卫共用的选中态重置收口 — 小欧-2026-09-24
  // 2026-09-25 小欧 - 5.2-1：勾选重置为目标 Provider 已配置集（原空集与设计字面不符）— 小欧-2026-09-25
  const resetSelection = (providerName: string) => {
    const p = providers.find((x) => x.name === providerName);
    setRemote(null);
    setChecked(new Set((p?.models ?? []).map((m) => m.name)));
    setKeyword('');
    setFetchError(null);
  };

  // §5.2-7：providers 变化（设置页增删/外部改 yaml）时本地 selectedProvider 失效守卫
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

  // D4 三项过滤叠加：关键词 + 仅看免费（分组在渲染层做）
  const filtered = useMemo(() => {
    if (!remote?.ok) return [];
    const kw = keyword.trim().toLowerCase();
    return remote.models.filter((m) => {
      if (freeOnly && !isFreeModel(m.id)) return false;
      if (
        kw &&
        !m.id.toLowerCase().includes(kw) &&
        !(m.owned_by ?? '').toLowerCase().includes(kw)
      )
        return false;
      return true;
    });
  }, [remote, keyword, freeOnly]);

  const { configuredGroup, unconfiguredGroup } = useMemo(() => {
    const configuredSet = new Set(remote?.configured ?? []);
    const configured: typeof filtered = [];
    const unconfigured: typeof filtered = [];
    for (const m of filtered) {
      (configuredSet.has(m.id) ? configured : unconfigured).push(m);
    }
    return { configuredGroup: configured, unconfiguredGroup: unconfigured };
  }, [filtered, remote]);

  // D2 替换式：勾选集 = 最终列表；远端未回但配置里仍有的模型自动保留（防静默丢配置）
  const finalList = useMemo(() => {
    if (!remote?.ok) return [];
    const listed = new Set(remote.models.map((m) => m.id));
    const preserve = remote.configured.filter((id) => !listed.has(id));
    return [
      ...remote.models.map((m) => m.id).filter((id) => checked.has(id)),
      ...preserve,
    ];
  }, [remote, checked]);
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
        </span>
      ),
      onOk: async () => {
        setSaving(true);
        try {
          const res = await modelApi.replaceModels(selectedProvider, finalList);
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

  const renderRow = (m: { id: string; owned_by?: string | null }) => {
    const isCurrent = remote?.current_model === m.id;
    return (
      <div key={m.id} style={settingsRowStyle}>
        <Checkbox
          checked={isCurrent || checked.has(m.id)}
          disabled={isCurrent}
          onChange={() => toggle(m.id)}
        />
        <span
          style={{
            marginLeft: Spacing.MD,
            fontSize: FontSize.PRIMARY,
            flex: 1,
          }}
        >
          {m.id}
        </span>
        {m.owned_by && (
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
              marginRight: Spacing.MD,
            }}
          >
            {m.owned_by}
          </span>
        )}
        {isCurrent && <Tag>当前</Tag>}
      </div>
    );
  };

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
        {rows.map(renderRow)}
      </div>
    );

  return (
    <div>
      <SectionTitle title="── ① 获取 ──" />
      <div style={{ display: 'flex', gap: Spacing.MD, alignItems: 'center' }}>
        <Select
          value={selectedProvider}
          style={{ width: settingsControl.modelSelectWidth }}
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
        {apiBaseEmpty && (
          <span
            style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.WEAK }}
          >
            未配置 api_base，请先到模型 Tab → ③ Provider 配置填写
          </span>
        )}
      </div>
      {fetchError && (
        <Alert
          style={{ marginTop: Spacing.MD }}
          type="error"
          showIcon
          message={fetchError}
        />
      )}

      <SectionTitle title="── ② 过滤 ──" />
      <div style={{ display: 'flex', gap: Spacing.MD, alignItems: 'center' }}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索模型名 / 作者"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: settingsControl.searchWidth }}
        />
        <Tooltip title="只显示名称含 -free 或 big-pickle 的模型">
          <Checkbox
            checked={freeOnly}
            onChange={(e) => setFreeOnly(e.target.checked)}
            style={{ fontSize: FontSize.SECONDARY }}
          >
            仅看免费
          </Checkbox>
        </Tooltip>
      </div>
      {remote?.ok && (
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginTop: Spacing.XS,
          }}
        >
          共 {remote.models.length} 个模型，已配置 {remote.configured.length}{' '}
          个，已勾选 {finalList.length} 个
        </div>
      )}

      <SectionTitle title="── ③ 列表 ──" />
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

      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginTop: Spacing.LG,
        }}
      >
        <Button
          type="primary"
          disabled={!remote?.ok || finalList.length === 0}
          loading={saving}
          onClick={onSave}
        >
          保存所选（{finalList.length}）
        </Button>
      </div>
    </div>
  );
};
