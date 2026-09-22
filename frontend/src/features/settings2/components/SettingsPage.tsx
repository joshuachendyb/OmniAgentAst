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
// 2026-09-21 小强 - Tab 标题唯一源=后端注册表：删硬编码 TAB_TITLES（含死 chat:"聊天"），
//   Tab label 改用 state.schema[g].label（后端 settings_registry GROUPS[g].label）；GROUP_ORDER 由 useSettings 动态派生
// 2026-09-21 小强 - 关联清理：dangerousDirty 去掉已删键 whitelist/blacklist 死判断（键已从注册表移除，恒 false 死代码）
// 2026-09-21 小欧 - [59]F-6/F-7/F-9 修复：①搜索跳转 jumpTo 与 Tab 切换统一走「当前组脏→确认」闸口，
//   不再绕过确认直接切 Tab（原 jumpTo 静默丢弃当前组未保存修改）；确认对话框记录待跳 tab+高亮 key，
//   保存成功后跳转并高亮；②deleteTarget 解析改用首个 '::' 索引切片（原 split('::') 对含 '::' 的模型名截断误删）；
//   ③onSaveGroup/onSaveAll 返回 Promise，SaveBar confirmThen 的 Modal onOk await 化——OK 按钮自带 loading 防连点双保存
// 2026-09-21 小强 - 切 provider 表单值跟随真修复：key 加在 ProviderConfig 组件层（整体重挂→useForm 全新实例→空仓库→新 initialValues 落盘；内层 key 经 rc-field-form 源码证伪无效已删，北京老陈定）
// 2026-09-21 小强 - 设置页17问题复核修复（[设置页UI审计] 问题1/4/7/8/9/11/12/13/17）：
//   ①搜索跳转滚动到命中行(data-settings-key 锚点，双 rAF)；②切Tab确认文案与"保存并切换"行为对齐；
//   ③危险确认拆分本组/全部(dangerousGroup/All)，危险键含 security.enabled；④模型组脏计数按实际参数数；
//   ⑤添加/删除/Provider 保存失败不关窗并 rethrow（弹窗保留输入）；⑥添加 Provider toast 引导切换；
//   ⑦jumpToProviderConfig 走脏确认闸口+保存后滚动锚点；⑧删模型Tab①"当前系统全局使用模型"冗余行
// 2026-09-22 小强 - A3：ModelActions 传 envManaged（provider env 接管时隐藏「清空 api_key」，后端拒 clear）
// 2026-09-22 小欧 - [62]P3：ModelParams 传 options={state.model.paramOptions}（读链末端：state→组件；P4 才消费渲染 Select）
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
  handleError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';
import { isDirty } from '../utils/modelUtils';
import type { TabKey } from '../types';

const SettingsPage: React.FC = () => {
  const s = useSettings();
  const { state } = s;
  const [pendingJump, setPendingJump] = useState<{
    tab: TabKey;
    key: string;
    anchor?: string | null;
  } | null>(null);

  // [59]F-6 修复：requestTab 与 jumpTo（搜索高亮跳转）统一走「当前组脏→确认」闸口，
  // 原 jumpTo 直接切 Tab 绕过确认，会静默丢弃当前组未保存修改
  const requestTab = (tab: TabKey) => {
    if (tab !== state.activeTab && s.isGroupDirty(state.activeTab)) {
      setPendingJump({ tab, key: '' });
    } else {
      s.setActiveTab(tab);
      void s.checkMtime();
    }
  };

  // 修正(2026-09-21 小强)：搜索跳转滚动到命中行——原仅高亮无 scrollIntoView，跨 Tab/长列表定位不到
  // （[设置页UI审计] 问题1）；双 rAF 等目标 Tab DOM 挂载后滚动
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

  // 第五章 S2/S3：滚动跳转（跨 Tab 锚点：先切到目标 Tab，等渲染完成后再滚动）
  const scrollTo = (dataSection: string) => {
    const el = document.querySelector(`[data-section="${dataSection}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  // 修正(2026-09-21 小强)：jumpToProviderConfig 也走「当前组脏→确认」闸口——
  // 原直调 setActiveTab 绕过确认切到模型 Tab（[设置页UI审计] 问题11）
  const jumpToProviderConfig = () => {
    if (s.isGroupDirty(state.activeTab)) {
      setPendingJump({ tab: 'model', key: '', anchor: 'provider-config' });
      return;
    }
    s.setActiveTab('model');
    requestAnimationFrame(() => scrollTo('provider-config'));
  };

  // 修正(2026-09-21 小强)：危险判定拆分「保存本组/保存全部」——原全局判定致保存其它组误弹；
  // 危险键=安全开关/危险操作确认的变更（含 security.enabled 关闭场景，原仅认 confirmDangerousOps）
  // （[设置页UI审计] 问题7/8）
  const DANGEROUS_KEYS = ['security.enabled', 'security.confirmDangerousOps'];
  const dangerousGroup =
    state.activeTab === 'security' &&
    DANGEROUS_KEYS.some((k) => state.dirtyKeys[k]);
  const dangerousAll = DANGEROUS_KEYS.some((k) => state.dirtyKeys[k]);

  // 修正(2026-09-21 小强)：模型组脏计数按实际脏参数数（原是 isDirty?1:0 恒 1 项误导）（[设置页UI审计] 问题13）
  const groupDirtyCount =
    state.activeTab === 'model'
      ? Object.values(
          isDirty(
            state.model.params,
            state.model.defaults,
            state.model.envOverride
          )
        ).filter(Boolean).length
      : Object.keys(state.dirtyKeys).filter(
          (k) => s.groupOfKey(k) === state.activeTab
        ).length;

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
        {/* 修正(2026-09-21 小强)：删除「当前系统全局使用模型」冗余小字——该信息已由
            通用 Tab CurrentModelRefCard 完整展示（标题+卡内文案），此处重复（[设置页UI审计] 问题17） */}
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
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <SectionTitle title="── ② 参数区（跟随当前模型） ──" />
        {Object.keys(state.model.params).length > 0 && (
          <Button
            type="link"
            style={{ padding: 0, color: Colors.TEXT.SECONDARY }}
            disabled={!state.model.isDirty}
            onClick={() => {
              Modal.confirm({
                title: (
                  <span
                    style={{
                      fontSize: FontSize.PRIMARY,
                      fontWeight: FontWeight.BOLD,
                    }}
                  >
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
        options={state.model.paramOptions}
        envOverride={state.model.envOverride}
        onChange={s.setParam}
      />
      <div data-section="provider-config">
        <SectionTitle title="── ③ Provider 配置 ──" />
        <ProviderConfig
          key={state.model.selectedProvider}
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
              // 修正(2026-09-21 小强)：查 ok——后端配置错误回 HTTP200+ok:false 时不查会弹假成功；
              //   失败 rethrow，ProviderConfig 才不执行 api_key 复位（[设置页UI审计] 问题6）
              if (!r.ok) {
                handleError({
                  message: 'Provider 配置保存失败',
                  error_type: ErrorType.MODEL_CONFIG_ERROR,
                });
                throw new Error('provider-config-save-failed');
              }
              showSuccess('Provider 配置已保存（立即生效）');
              // A7：同步落盘后 mtime
              s.syncMtime(r.mtime);
              await s.refreshModels();
            } catch (e) {
              handleApiError(e);
              throw e;
            }
          }}
        />
      </div>
      <SectionTitle title="── ④ 操作区 ──" />
      <ModelActions
        configured={
          state.model.providerConfig[state.model.selectedProvider]?.api_key
            ?.configured ?? false
        }
        // A3(2026-09-22 小强)：env 接管 provider 隐藏「清空 api_key」（后端拒 clear）
        envManaged={
          state.model.providerConfig[state.model.selectedProvider]?.env ?? false
        }
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
            // 修正(2026-09-21 小强)：成功才关窗（原 catch 外统一关，保存失败也关+输入被清）；失败 rethrow 让弹窗保留输入（[设置页UI审计] 问题9）
            s.patchModel({ addModelModalOpen: false });
          } catch (e) {
            handleApiError(e);
            throw e;
          }
        }}
        onSubmitAddProvider={async (d) => {
          try {
            const res = await modelApi.addProvider(d);
            s.syncMtime(res.mtime);
            // 修正(2026-09-21 小强)：添加后引导切换新 Provider 配置区——原无任何引导、③区停留旧 Provider（[设置页UI审计] 问题12）
            showSuccess('Provider 已添加，请在①选择器切换到新 Provider 配置');
            await s.refreshModels();
            s.patchModel({ addProviderModalOpen: false });
          } catch (e) {
            handleApiError(e);
            throw e;
          }
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
              // [59]F-7 修复：改用首个 '::' 索引切片，模型名含 '::' 时不再被 split 截断误删
              const rest = target.slice('model:'.length);
              const sepIndex = rest.indexOf('::');
              const p = sepIndex >= 0 ? rest.slice(0, sepIndex) : '';
              const m = sepIndex >= 0 ? rest.slice(sepIndex + 2) : rest;
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
            // 修正(2026-09-21 小强)：成功才关删除确认（原 catch 外统一关，失败也关，用户看不到错因）（[设置页UI审计] 问题9）
            s.patchModel({ deleteConfirmOpen: false, deleteTarget: null });
          } catch (e) {
            handleApiError(e);
          }
        }}
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
                    {SettingIcon[g]} {state.schema[g]?.label ?? g}
                  </span>
                ),
              }))}
            />
            <span style={{ marginLeft: Spacing.MD }}>
              <DirtyBadge count={s.dirtyCount} />
            </span>
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
          dangerousGroup={dangerousGroup}
          dangerousAll={dangerousAll}
          // [59]F-9 修复：直接透出 Promise，SaveBar 确认弹窗 onOk await 化后自带 loading 防连点
          onSaveGroup={() => s.saveGroup(state.activeTab)}
          onSaveAll={() => s.saveAll()}
          onCloseRestart={() => s.setRestartKeys([])}
        />
      </Card>
      <Modal
        open={pendingJump !== null}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            有未保存的修改
          </span>
        }
        width={settingsModalWidth.confirm}
        onCancel={() => setPendingJump(null)}
        onOk={() => {
          const jump = pendingJump;
          if (!jump) return;
          void s.saveGroup(state.activeTab).then((r) => {
            if ((r as { ok: boolean }).ok) {
              s.setActiveTab(jump.tab);
              if (jump.key) {
                s.setHighlightKey(jump.key);
                scrollToKey(jump.key);
              }
              // 修正(2026-09-21 小强)：确认保存成功后滚动到待跳锚点（添加 Provider 引导场景）（[设置页UI审计] 问题11）
              if (jump.anchor)
                requestAnimationFrame(() => scrollTo(jump.anchor as string));
            }
            setPendingJump(null);
          });
        }}
        okText="保存并切换"
        cancelText="放弃切换"
      >
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          {/* 修正(2026-09-21 小强)：文案与行为对齐——原"修改将丢失"与"保存并切换"自相矛盾，
              实际是保存后切换/取消则留在本页（修改不丢）（[设置页UI审计] 问题4） */}
          当前组存在未保存修改：点击「保存并切换」将保存当前修改后跳转；点击「放弃切换」将留在本页，修改不会丢失。
        </span>
      </Modal>
    </div>
  );
};

export default SettingsPage;
