// 编辑历史: 2026-09-20 小强 - 新建：设置页壳（搜索+Tabs+全局脏角标+切 Tab 未保存确认内联+sticky 保存条，见 7.2/6.4）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：message.success/info 改走 errorHandler.showSuccess/showMessage
// 2026-09-21 小强 - BUG-F 修复：模型删除确认的 target 精确匹配 provider::model（原 deleteTarget 未带 provider
//   前缀，确认句恒为 false 导致删除项参数名链上错误——匹配 SettingRow 的 key 形如 provider::model）
// 2026-09-21 小欧 - P0-1+P0-5：背景色→Colors.BG.PRIMARY、字重→FontWeight.BOLD、间距→Spacing（[58] P0-1/P0-5）
// 2026-09-21 小欧 - P1-3：保存本组按钮带本组待存计数（[58] P1-3）
// 2026-09-21 小欧 - P1-4：重置按钮上移到②标题行右侧（方案B）+ 顺带修正：无params隐藏/无脏态disabled（[58] P1-4）
// 2026-09-21 小欧 - 第五章：当前生效模型高占位状态卡集成（[58] 第五章 5.6）
// 2026-09-21 小欧 - 第五章核查修复：小字可点跳模型 Tab；S2/S3 锚点滚动+高亮（Step 5.2/5.3）；第六章 6.4 重置确认弹窗 danger+⚠（[58] v1.11）
// 2026-09-21 小欧 - 全文逐章核查：④重置确认/⑦Tab切换 弹窗宽散落 480 → settingsModalWidth.confirm 令牌收口（[58] v1.12 第六章 6.1 规范一）
// 2026-09-21 小欧 - 排版重构：CurrentModelRefCard+参数区从模型Tab移到通用Tab；模型Tab区块编号④→③；删除Card顶部辅位小字（与通用Tab CurrentModelRefCard重复）；新增沙箱Tab
// 2026-09-21 小欧 - 模型Tab：①选择器上方加"当前系统全局使用模型"行（与通用Tab CurrentModelRefCard 对应）；删废弃 jumpToModels
// 2026-09-21 小欧 - 修正排版重构失误：参数区（ModelParams/模型特殊参数）从通用Tab移回模型Tab，模型Tab恢复四区块②参数区；ProviderConfig补max_retries回退值
// 2026-09-21 小欧 - 三堂会审修复：删除无触发源死代码 highlightJump/flashSelector（YAGNI，消 eslint pre-existing warning）；
//   jumpToProviderConfig 修复跨Tab失效（CurrentModelRefCard 已移通用Tab，原 scrollTo 在模型Tab未渲染时静默失败）
// 2026-09-21 小欧 - 方案A：删除 Provider/模型成功后由 refreshModels 改整体 load()，焦点/全局卡/参数区重载对齐后端
//   （根治"删全局当前模型时前端仍悬浮已删模型，保存报错、全局卡显示假数据"）——[54] v4.20 关联
import React, { useState } from 'react';
import { Button, Card, Modal, Result, Skeleton, Tabs } from 'antd';
import { Colors, FontSize, Spacing, FontWeight } from '@/utils/stepStyles';
import { settingsSpacing, settingsModalWidth } from '@/theme/settingsTokens';
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
import { SectionTitle } from './SectionTitle';
import { CurrentModelRefCard } from './CurrentModelRefCard';
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
  sandbox: '沙箱',
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

  // 第五章 S2/S3：滚动跳转（跨 Tab 锚点：先切到目标 Tab，等渲染完成后再滚动）
  const scrollTo = (dataSection: string) => {
    const el = document.querySelector(`[data-section="${dataSection}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  const jumpToProviderConfig = () => {
    s.setActiveTab('model');
    requestAnimationFrame(() => scrollTo('provider-config'));
  };

  const dangerousDirty = Object.keys(state.dirtyKeys).some(
    (k) =>
      k.includes('confirmDangerousOps') ||
      k.includes('whitelist') ||
      k.includes('blacklist')
  );

  const groupDirtyCount = state.activeTab === 'model'
    ? (state.model.isDirty ? 1 : 0)
    : Object.keys(state.dirtyKeys).filter((k) => s.groupOfKey(k) === state.activeTab).length;

  if (state.loading) {
    return (
      <div
        className="settings-page"
        style={{ padding: settingsSpacing.pagePadding, background: Colors.BG.PRIMARY }}
      >
        <Skeleton active />
      </div>
    );
  }
  if (state.loadError) {
    return (
      <div
        className="settings-page"
        style={{ padding: settingsSpacing.pagePadding, background: Colors.BG.PRIMARY }}
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

  const renderGeneralTab = () => (
    <div>
      <CurrentModelRefCard
        currentRef={state.currentRef}
        providers={state.model.providers}
        onModelSwitched={() => void s.load()}
        onAddProvider={jumpToProviderConfig}
      />
      <SettingsGroup
        group="general"
        items={state.schema['general']?.items ?? []}
        values={state.values['general'] ?? {}}
        sources={state.sources['general'] ?? {}}
        dirtyKeys={state.dirtyKeys}
        highlightKey={s.highlightKey}
        onChange={s.setValue}
      />
    </div>
  );

  const renderModelTab = () => (
    <div>
      <div
        data-section="selector"
        style={{
          borderRadius: settingsSpacing.pagePadding,
          padding: `0 ${Spacing.MD}px`,
          margin: `0 -${Spacing.MD}px`,
        }}
      >
        {state.currentRef && (
          <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY, marginBottom: Spacing.SM }}>
            当前系统全局使用模型：{state.currentRef.provider} / {state.currentRef.model}
          </div>
        )}
        <SectionTitle title="── ① 选择器 ──" />
        <ModelSelector
          providers={state.model.providers}
          selectedProvider={state.model.selectedProvider}
          selectedModel={state.model.selectedModel}
          onSelectProvider={s.selectProvider}
          onSelectModel={s.selectModel}
          onAddModel={() => s.patchModel({ addModelModalOpen: true })}
          onAddProvider={() => s.patchModel({ addProviderModalOpen: true })}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <SectionTitle title="── ② 参数区（跟随当前模型） ──" />
        {Object.keys(state.model.params).length > 0 && (
          <Button
            type="link"
            style={{ padding: 0, color: Colors.TEXT.SECONDARY }}
            disabled={!state.model.isDirty}
            onClick={() => {
              Modal.confirm({
                title: (
                  <span style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}>
                    ⚠ 重置为默认
                  </span>
                ),
                content: (
                  <span style={{ color: Colors.TEXT.SECONDARY }}>
                    将恢复该模型全部参数为默认值，当前修改将丢失。
                  </span>
                ),
                okText: '确认重置',
                okButtonProps: { danger: true },
                cancelText: '取消',
                width: settingsModalWidth.confirm,
                onOk: () => s.resetParams(),
              });
            }}
          >
            重置为默认
          </Button>
        )}
      </div>
      <ModelParams
        params={state.model.params}
        defaults={state.model.defaults}
        ranges={state.model.ranges}
        envOverride={state.model.envOverride}
        onChange={s.setParam}
      />
      <div data-section="provider-config">
        <SectionTitle title="── ③ Provider 配置 ──" />
        <ProviderConfig
          name={state.model.selectedProvider}
          config={
            state.model.providerConfig[state.model.selectedProvider] ?? {
              api_key: { configured: false, suffix: '' },
              base_url: '',
              timeout: 60,
              max_retries: 3,
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
      </div>
      <SectionTitle title="── ④ 操作区 ──" />
      <ModelActions
        configured={state.model.providerConfig[state.model.selectedProvider]?.api_key?.configured ?? false}
        onClearApiKey={async () => {
          try {
            const r = await modelApi.updateProvider(
              state.model.selectedProvider,
              { clear: true }
            );
            showSuccess('api_key 已清空');
            s.syncMtime(r.mtime);
            await s.refreshModels();
          } catch (e) {
            handleApiError(e);
          }
        }}
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
            // v4.20(小欧 2026-09-21 方案A)：删除后整体 load()——焦点(selectedProvider/Model)/currentRef/参数区
            //   全部重载对齐后端，杜绝「删的是全局当前模型时前端仍停在已删模型上(悬空+保存报错)」
            await s.load();
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
      style={{ padding: settingsSpacing.pagePadding, background: Colors.BG.PRIMARY }}
    >
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: Spacing.LG,
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
            <span style={{ marginLeft: Spacing.MD }}><DirtyBadge count={s.dirtyCount} /></span>
          </span>
          <SearchBox schema={state.schema} onJump={jumpTo} />
        </div>
        {state.activeTab === 'model' ? (
          renderModelTab()
        ) : state.activeTab === 'general' ? (
          renderGeneralTab()
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
          groupDirtyCount={groupDirtyCount}
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
        title={
          <span style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}>
            有未保存的修改
          </span>
        }
        width={settingsModalWidth.confirm}
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
        cancelText="放弃切换"
      >
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          切换 Tab 后未保存的修改将丢失，需手动还原。
        </span>
      </Modal>
    </div>
  );
};

export default SettingsPage;
