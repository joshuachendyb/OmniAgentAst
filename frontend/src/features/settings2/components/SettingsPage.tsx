// 编辑历史: 2026-09-20 小强 - 新建：设置页壳（搜索+Tabs+组级脏点+切 Tab 未保存确认+保存条）。
// 2026-11-09 小欧 - 模型区版式/实测/增删逻辑拆至 ModelTab 与 useCapabilityProbe/useModelActions，本文件只留壳与跨 Tab 编排 — 小欧-2026-11-09
// 2026-11-09 小欧 - 删 saveGroup 返回值的冗余类型断言（SaveResult.ok 已是 boolean）— 小欧-2026-11-09
import React, { useMemo, useState } from 'react';
import { Button, Card, Result, Skeleton, Tabs } from 'antd';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import { settingsSpacing } from '@/theme/settingsTokens';
import { SettingsModal } from '@/theme/SettingsModal';
import { useSettings } from '../hooks/useSettings';
import { useCapabilityProbe } from '../hooks/useCapabilityProbe';
import { useModelActions } from '../hooks/useModelActions';
import { SettingsGroup } from './SettingsGroup';
import { SearchBox } from './SearchBox';
import { SaveBar } from './SaveBar';
import { SettingIcon, TabDirtyDot } from './icons';
import { ModelModals } from './ModelModals';
import { CurrentModelRefCard } from './CurrentModelRefCard';
import { ModelLibraryTab } from './ModelLibraryTab';
import { ModelTab } from './ModelTab';
import {
  buildDangerChanges,
  buildDangerHints,
  pickDangerDirtyKeys,
} from '../constants/dangerKeys';
import { modelDirtyCount } from '../utils/modelUtils';
import type { TabKey } from '../types';

const SettingsPage: React.FC = () => {
  const s = useSettings();
  const { state } = s;
  // 跨 Tab 跳转意图：key=搜索命中高亮键，anchor=区块锚点
  const [pendingJump, setPendingJump] = useState<{
    tab: TabKey;
    key: string;
    anchor?: string | null;
  } | null>(null);
  // 放弃修改后自增：ProviderConfig 以 key 重挂载，按已保存配置重新回显本地输入
  const [providerResetSeq, setProviderResetSeq] = useState(0);
  // Image_URL 输入缓冲：undefined=未编辑，失焦/回车即存
  const [probeUrlDraft, setProbeUrlDraft] = useState<string | undefined>(
    undefined
  );
  // 弹窗/表单开关属视图态，不进领域 state
  const [addModelOpen, setAddModelOpen] = useState(false);
  const [addProviderOpen, setAddProviderOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [addParamFormOpen, setAddParamFormOpen] = useState(false);
  const [paramOptionsModalOpen, setParamOptionsModalOpen] = useState(false);

  const probe = useCapabilityProbe(s);
  const actions = useModelActions(s, {
    deleteTarget,
    closeAddModel: () => setAddModelOpen(false),
    closeAddProvider: () => setAddProviderOpen(false),
    closeDelete: () => {
      setDeleteOpen(false);
      setDeleteTarget(null);
    },
  });

  // requestTab 与 jumpTo（搜索高亮跳转）统一走「当前组脏→确认」闸口，不静默丢弃未保存修改
  const requestTab = (tab: TabKey) => {
    if (tab !== state.activeTab && s.isGroupDirty(state.activeTab)) {
      setPendingJump({ tab, key: '' });
    } else {
      s.setActiveTab(tab);
      void s.checkMtime();
    }
  };

  // 双 rAF 等目标 Tab DOM 挂载后滚动
  const scrollToKey = (itemKey: string) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = document.querySelector(`[data-settings-key="${itemKey}"]`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    });
  };

  const jumpTo = (tab: TabKey, key: string) => {
    if (tab !== state.activeTab && s.isGroupDirty(state.activeTab)) {
      setPendingJump({ tab, key });
    } else {
      s.setActiveTab(tab);
      s.setHighlightKey(key);
      scrollToKey(key);
    }
  };

  const scrollTo = (dataSection: string) => {
    const el = document.querySelector(`[data-section="${dataSection}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  // 跳转目标组是 model（本函数唯一调用点在通用 Tab）
  const jumpToProviderConfig = () => {
    if (s.isGroupDirty('model')) {
      setPendingJump({ tab: 'model', key: '', anchor: 'provider-config' });
      return;
    }
    s.setActiveTab('model');
    requestAnimationFrame(() => scrollTo('provider-config'));
  };

  const dangerDirtyKeys = useMemo(
    () => pickDangerDirtyKeys(state.dirtyKeys),
    [state.dirtyKeys]
  );
  const dangerChanges = useMemo(
    () =>
      buildDangerChanges(
        dangerDirtyKeys,
        state.values,
        state.baseline,
        s.groupOfKey
      ),
    [dangerDirtyKeys, state.values, state.baseline, s.groupOfKey]
  );
  const dangerHintByChange = useMemo(
    () => buildDangerHints(dangerDirtyKeys, state.values, s.groupOfKey),
    [dangerDirtyKeys, state.values, s.groupOfKey]
  );
  // 危险判定拆「本组/全部」：原全局判定致保存其它组误弹
  const dangerousGroup =
    state.activeTab === 'security' && dangerDirtyKeys.length > 0;
  const dangerousAll = dangerDirtyKeys.length > 0;

  // env 接管单点：能力行为空时 envOverride 判不出，须读 providerConfig.env
  const envManaged =
    state.model.providerConfig[state.model.selectedProvider]?.env === true;

  // 模型组计数与 hook 同源；其它组按 schema 归属过滤
  const groupDirtyCount =
    state.activeTab === 'model'
      ? modelDirtyCount(state.model)
      : Object.keys(state.dirtyKeys).filter(
          (k) => s.groupOfKey(k) === state.activeTab
        ).length;

  const discardModel = () => {
    s.discardGroup('model');
    setProviderResetSeq((x) => x + 1);
  };

  // Image_URL 即存：缓冲先清、写入走 hook 的守卫链
  const saveProbeUrl = () => {
    if (probeUrlDraft === undefined) return;
    const v = probeUrlDraft;
    setProbeUrlDraft(undefined);
    void s.saveProbeImageUrl(v);
  };

  /** 切 Tab 确认弹窗的「放弃并切换」：只撤当前组，模型组额外重挂 Provider 配置 */
  const discardAndJump = (jump: {
    tab: TabKey;
    key: string;
    anchor?: string | null;
  }) => {
    s.discardGroup(state.activeTab);
    if (state.activeTab === 'model') setProviderResetSeq((x) => x + 1);
    s.setActiveTab(jump.tab);
    if (jump.key) {
      s.setHighlightKey(jump.key);
      scrollToKey(jump.key);
    }
    if (jump.anchor)
      requestAnimationFrame(() => scrollTo(jump.anchor as string));
  };

  if (state.loading) {
    return (
      <div
        className="settings-page"
        style={{
          padding: settingsSpacing.pagePadding,
          background: Colors.BG.PRIMARY,
        }}
      >
        <Skeleton active />
      </div>
    );
  }
  if (state.loadError) {
    return (
      <div
        className="settings-page"
        style={{
          padding: settingsSpacing.pagePadding,
          background: Colors.BG.PRIMARY,
        }}
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

  return (
    <div
      className="settings-page"
      style={{
        padding: settingsSpacing.pagePadding,
        background: Colors.BG.PRIMARY,
      }}
    >
      {/* 弹窗走 portal 挂 body，提到页面顶层：model_library Tab 的「添加 Provider」也要能唤起 */}
      <ModelModals
        providers={state.model.providers}
        addModelOpen={addModelOpen}
        addProviderOpen={addProviderOpen}
        deleteOpen={deleteOpen}
        deleteTarget={deleteTarget}
        selectedProvider={state.model.selectedProvider}
        onCloseAddModel={() => setAddModelOpen(false)}
        onCloseAddProvider={() => setAddProviderOpen(false)}
        onCloseDelete={() => {
          setDeleteOpen(false);
          setDeleteTarget(null);
        }}
        onSubmitAddModel={actions.submitAddModel}
        onSubmitAddProvider={actions.submitAddProvider}
        onConfirmDelete={actions.confirmDelete}
      />
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: Spacing.SM,
          }}
        >
          <span>
            <Tabs
              type="line"
              activeKey={state.activeTab}
              onChange={(k) => requestTab(k as TabKey)}
              // 归零 antd 自带 16px，避免与 Card padding 叠成大片空白
              tabBarStyle={{ marginBottom: 0 }}
              items={s.GROUP_ORDER.map((g) => ({
                key: g,
                // 组级脏点常显占位：亮=该组有未保存，灭=透明占位保持列宽零跳变
                label: (
                  <span
                    style={{ display: 'inline-flex', alignItems: 'center' }}
                  >
                    {SettingIcon[g]} {state.schema[g]?.label ?? g}
                    <TabDirtyDot on={s.isGroupDirty(g)} />
                  </span>
                ),
              }))}
            />
          </span>
          <SearchBox schema={state.schema} onJump={jumpTo} />
        </div>
        {state.activeTab === 'model' ? (
          <ModelTab
            s={s}
            probe={probe}
            envManaged={envManaged}
            providerResetSeq={providerResetSeq}
            probeUrlDraft={probeUrlDraft}
            onProbeUrlChange={setProbeUrlDraft}
            onProbeUrlSave={saveProbeUrl}
            addParamFormOpen={addParamFormOpen}
            onAddParamFormOpen={() => setAddParamFormOpen(true)}
            onAddParamFormClose={() => setAddParamFormOpen(false)}
            paramOptionsModalOpen={paramOptionsModalOpen}
            onParamOptionsOpen={() => setParamOptionsModalOpen(true)}
            onParamOptionsClose={() => setParamOptionsModalOpen(false)}
            onDiscard={discardModel}
            onAddModel={() => setAddModelOpen(true)}
            onAddProvider={() => setAddProviderOpen(true)}
            onClearApiKey={actions.clearApiKey}
            onDeleteModel={() => {
              setDeleteTarget(
                `model:${state.model.selectedProvider}::${state.model.selectedModel}`
              );
              setDeleteOpen(true);
            }}
            onDeleteProvider={() => {
              setDeleteTarget(`provider:${state.model.selectedProvider}`);
              setDeleteOpen(true);
            }}
          />
        ) : state.activeTab === 'general' ? (
          renderGeneralTab()
        ) : state.activeTab === 'model_library' ? (
          <ModelLibraryTab
            providers={state.model.providers}
            onSaved={actions.afterModelSaved}
            onAddProvider={() => setAddProviderOpen(true)}
          />
        ) : (
          <SettingsGroup
            group={state.activeTab}
            items={state.schema[state.activeTab]?.items ?? []}
            values={state.values[state.activeTab] ?? {}}
            sources={state.sources[state.activeTab] ?? {}}
            dirtyKeys={state.dirtyKeys}
            highlightKey={s.highlightKey}
            onChange={s.setValue}
            // secret 项落盘后用 load(keepModel) 刷新掩码，不能走 setValue 置脏
            onRefresh={() => void s.load({ keepModel: true })}
          />
        )}
        <SaveBar
          canSaveGroup={s.isGroupDirty(state.activeTab)}
          canSaveAll={s.dirtyCount > 0}
          dirtyCount={s.dirtyCount}
          groupDirtyCount={groupDirtyCount}
          saving={s.saving}
          restartKeys={s.restartKeys}
          dangerousGroup={dangerousGroup}
          dangerousAll={dangerousAll}
          dangerChanges={dangerChanges}
          dangerHintByChange={dangerHintByChange}
          onSaveGroup={() => s.saveGroup(state.activeTab)}
          onSaveAll={() => s.saveAll()}
          onCloseRestart={() => s.setRestartKeys([])}
        />
      </Card>
      <SettingsModal
        open={pendingJump !== null}
        title="有未保存的修改"
        width="confirm"
        confirmLoading={s.saving}
        onCancel={() => setPendingJump(null)}
        footer={[
          <Button key="stay" onClick={() => setPendingJump(null)}>
            留在本页
          </Button>,
          <Button
            key="discard"
            danger
            onClick={() => {
              const jump = pendingJump;
              setPendingJump(null);
              if (!jump) return;
              discardAndJump(jump);
            }}
          >
            放弃修改并切换
          </Button>,
          <Button
            key="save"
            type="primary"
            loading={s.saving}
            onClick={() => {
              const jump = pendingJump;
              if (!jump) return;
              void s.saveGroup(state.activeTab).then((r) => {
                if (r.ok) {
                  s.setActiveTab(jump.tab);
                  if (jump.key) {
                    s.setHighlightKey(jump.key);
                    scrollToKey(jump.key);
                  }
                  if (jump.anchor)
                    requestAnimationFrame(() =>
                      scrollTo(jump.anchor as string)
                    );
                }
                setPendingJump(null);
              });
            }}
          >
            保存并切换
          </Button>,
        ]}
      >
        {/* 正文只讲后果，按钮名由按钮承载 */}
        <div
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
        >
          当前组有未保存的修改：
          <ul style={{ margin: `${Spacing.SM}px 0 0`, paddingLeft: 20 }}>
            <li>保存并切换：－改动写入配置文件后跳转</li>
            <li>放弃修改并切换：－本次改动丢弃、不可恢复，直接跳转</li>
            <li>留在本页：－改动保留不丢，弹窗关闭</li>
          </ul>
        </div>
      </SettingsModal>
    </div>
  );
};

export default SettingsPage;
