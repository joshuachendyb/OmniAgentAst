// 编辑历史: 2026-09-20 小强 - 新建：设置页壳（搜索+Tabs+全局脏角标+切 Tab 未保存确认内联+sticky 保存条，见 7.2/6.4）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：message.success/info 改走 errorHandler.showSuccess/showMessage
import React, { useState } from 'react';
import { Button, Card, Modal, Result, Skeleton, Tabs } from 'antd';
import { settingsSpacing } from '@/theme/settingsTokens';
import { useSettings } from '../hooks/useSettings';
import { SettingsGroup } from './SettingsGroup';
import { SearchBox } from './SearchBox';
import { SaveBar } from './SaveBar';
import { DirtyBadge } from './DirtyBadge';
import { SettingIcon } from './icons';
import { ModelSelector } from './ModelSelector';
import { ModelParams } from './ModelParams';
import { ProviderConfig } from './ProviderConfig';
import { ModelActions } from './ModelActions';
import { ModelModals } from './ModelModals';
import { modelApi } from '@/services/api/model.api';
import {
  ErrorType,
  handleApiError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';
import type { TabKey } from '../types';

const TAB_TITLES: Record<TabKey, string> = {
  general: '通用',
  model: '模型',
  security: '安全',
  chat: '聊天',
  appearance: '外观',
  system: '系统',
};

const SettingsPage: React.FC = () => {
  const s = useSettings();
  const { state } = s;
  const [pendingTab, setPendingTab] = useState<TabKey | null>(null);

  const requestTab = (tab: TabKey) => {
    if (tab !== state.activeTab && s.isGroupDirty(state.activeTab)) {
      setPendingTab(tab);
    } else {
      s.setActiveTab(tab);
      void s.checkMtime();
    }
  };

  const jumpTo = (tab: TabKey, key: string) => {
    s.setActiveTab(tab);
    s.setHighlightKey(key);
  };

  const dangerousDirty = Object.keys(state.dirtyKeys).some(
    (k) =>
      k.includes('confirmDangerousOps') ||
      k.includes('whitelist') ||
      k.includes('blacklist')
  );

  if (state.loading) {
    return (
      <div
        className="settings-page"
        style={{ padding: settingsSpacing.pagePadding, background: '#fff' }}
      >
        <Skeleton active />
      </div>
    );
  }
  if (state.loadError) {
    return (
      <div
        className="settings-page"
        style={{ padding: settingsSpacing.pagePadding, background: '#fff' }}
      >
        <Result
          status="error"
          title="设置加载失败"
          subTitle={state.loadError}
          extra={
            <Button
              onClick={() => {
                void s.load();
              }}
            >
              重试
            </Button>
          }
        />
      </div>
    );
  }

  const renderModelTab = () => (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>① 选择器</div>
      <ModelSelector
        providers={state.model.providers}
        selectedProvider={state.model.selectedProvider}
        selectedModel={state.model.selectedModel}
        onSelectProvider={s.selectProvider}
        onSelectModel={s.selectModel}
        onAddModel={() => s.patchModel({ addModelModalOpen: true })}
        onAddProvider={() => s.patchModel({ addProviderModalOpen: true })}
      />
      <div style={{ fontWeight: 600, margin: '12px 0 8px' }}>
        ② 参数区（跟随当前模型）
      </div>
      <ModelParams
        params={state.model.params}
        defaults={state.model.defaults}
        ranges={state.model.ranges}
        envOverride={state.model.envOverride}
        onChange={s.setParam}
        onReset={s.resetParams}
      />
      <div style={{ fontWeight: 600, margin: '12px 0 8px' }}>
        ③ Provider 配置
      </div>
      <ProviderConfig
        name={state.model.selectedProvider}
        config={
          state.model.providerConfig[state.model.selectedProvider] ?? {
            api_key: { configured: false, suffix: '' },
            base_url: '',
            timeout: 60,
            env: false,
          }
        }
        onSave={async (patch) => {
          try {
            const r = await modelApi.updateProvider(
              state.model.selectedProvider,
              patch
            );
            showSuccess('Provider 配置已保存（立即生效）');
            // A7：同步落盘后 mtime
            s.syncMtime(r.mtime);
            await s.refreshModels();
          } catch (e) {
            handleApiError(e);
          }
        }}
      />
      <div style={{ fontWeight: 600, margin: '12px 0 8px' }}>④ 操作区</div>
      <ModelActions
        onDeleteModel={() =>
          s.patchModel({
            deleteConfirmOpen: true,
            deleteTarget: `model:${state.model.selectedProvider}::${state.model.selectedModel}`,
          })
        }
        onDeleteProvider={() =>
          s.patchModel({
            deleteConfirmOpen: true,
            deleteTarget: `provider:${state.model.selectedProvider}`,
          })
        }
      />
      <ModelModals
        providers={state.model.providers}
        addModelOpen={state.model.addModelModalOpen}
        addProviderOpen={state.model.addProviderModalOpen}
        deleteOpen={state.model.deleteConfirmOpen}
        deleteTarget={state.model.deleteTarget}
        selectedProvider={state.model.selectedProvider}
        onCloseAddModel={() => s.patchModel({ addModelModalOpen: false })}
        onCloseAddProvider={() => s.patchModel({ addProviderModalOpen: false })}
        onCloseDelete={() =>
          s.patchModel({ deleteConfirmOpen: false, deleteTarget: null })
        }
        onSubmitAddModel={async (d) => {
          try {
            const res = await modelApi.addModel({
              provider: d.provider,
              model: d.model,
              label: d.label,
              ...(d.default_params ? { default_params: d.default_params } : {}),
            });
            s.syncMtime(res.mtime);
            showSuccess('模型已添加');
            await s.refreshModels({ provider: d.provider, model: d.model });
          } catch (e) {
            handleApiError(e);
          }
          s.patchModel({ addModelModalOpen: false });
        }}
        onSubmitAddProvider={async (d) => {
          try {
            const res = await modelApi.addProvider(d);
            s.syncMtime(res.mtime);
            showSuccess('Provider 已添加');
            await s.refreshModels();
          } catch (e) {
            handleApiError(e);
          }
          s.patchModel({ addProviderModalOpen: false });
        }}
        onConfirmDelete={async () => {
          const target = state.model.deleteTarget ?? '';
          try {
            let res;
            if (target.startsWith('provider:')) {
              res = await modelApi.deleteProvider(
                target.slice('provider:'.length)
              );
              if (res.switched_to)
                showMessage(
                  ErrorType.INFO,
                  `已切换回默认 Provider：${res.switched_to}`
                );
            } else {
              // BUG-F 修复：模型名可含 '/'（如 z-ai/glm-4.7），改用 '::' 分隔解析，杜绝删除错位
              const [p, m] = target.slice('model:'.length).split('::');
              res = await modelApi.deleteModel(p, m);
              if (res.switched_to)
                showMessage(
                  ErrorType.INFO,
                  `已切换回默认模型：${res.switched_to}`
                );
            }
            s.syncMtime(res.mtime);
            await s.refreshModels();
          } catch (e) {
            handleApiError(e);
          }
          s.patchModel({ deleteConfirmOpen: false, deleteTarget: null });
        }}
      />
    </div>
  );

  return (
    <div
      className="settings-page"
      style={{ padding: settingsSpacing.pagePadding, background: '#fff' }}
    >
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <span>
            <Tabs
              type="line"
              activeKey={state.activeTab}
              onChange={(k) => requestTab(k as TabKey)}
              items={s.GROUP_ORDER.map((g) => ({
                key: g,
                label: (
                  <span>
                    {SettingIcon[g]} {TAB_TITLES[g]}
                  </span>
                ),
              }))}
            />
            <DirtyBadge count={s.dirtyCount} />
          </span>
          <SearchBox schema={state.schema} onJump={jumpTo} />
        </div>
        {state.activeTab === 'model' ? (
          renderModelTab()
        ) : (
          <SettingsGroup
            group={state.activeTab}
            items={state.schema[state.activeTab]?.items ?? []}
            values={state.values[state.activeTab] ?? {}}
            sources={state.sources[state.activeTab] ?? {}}
            dirtyKeys={state.dirtyKeys}
            // 2026-09-21 小强 - 修复类型瑕疵：highlightKey 为 useSettings 独立 state（非 SettingsState 字段），直接引用返回值等价
            highlightKey={s.highlightKey}
            onChange={s.setValue}
          />
        )}
        <SaveBar
          canSaveGroup={s.isGroupDirty(state.activeTab)}
          canSaveAll={s.dirtyCount > 0}
          dirtyCount={s.dirtyCount}
          saving={s.saving}
          restartKeys={s.restartKeys}
          hasDangerousDirty={dangerousDirty}
          onSaveGroup={() => {
            void s.saveGroup(state.activeTab);
          }}
          onSaveAll={() => {
            void s.saveAll();
          }}
          onCloseRestart={() => s.setRestartKeys([])}
        />
      </Card>
      <Modal
        open={pendingTab !== null}
        title="有未保存的修改"
        onCancel={() => setPendingTab(null)}
        onOk={() => {
          if (pendingTab) {
            void s.saveGroup(state.activeTab).then((r) => {
              if ((r as { ok: boolean }).ok) s.setActiveTab(pendingTab);
              setPendingTab(null);
            });
          }
        }}
        okText="保存并切换"
        cancelText="取消"
      >
        目标 Tab 存在未保存项：保存并切换 /
        取消停留（放弃修改请手动还原后切换）。
      </Modal>
    </div>
  );
};

export default SettingsPage;
