// 编辑历史: 2026-11-09 小欧 - 新建：模型 Tab 版式编排（①选择器/②参数区/③配置/④操作区 + 三个弹窗），逻辑全部下沉到面板 — 小欧-2026-11-09
import React from 'react';
import { SectionTitle } from './SectionTitle';
import { ModelActions } from './ModelActions';
import { ParamOptionsModal } from './ParamOptionsModal';
import { ModelTabSelector } from './ModelTabSelector';
import { ModelTabParamsHeader } from './ModelTabParamsHeader';
import { ModelTabParams } from './ModelTabParams';
import { ModelTabInputModalities } from './ModelTabInputModalities';
import { ImageUrlRow } from './ImageUrlRow';
import { ModelTabMediaProbe } from './ModelTabMediaProbe';
import { ModelTabOutputModalities } from './ModelTabOutputModalities';
import { ModelTabGenProbe } from './ModelTabGenProbe';
import { ModelTabProviderConfig } from './ModelTabProviderConfig';
import { probeImageUrlOf } from '../utils/probeView';
import type { CapabilityProbe } from '../hooks/useCapabilityProbe';
import type { UseSettings } from '../hooks/useSettings';

interface Props {
  s: UseSettings;
  probe: CapabilityProbe;
  envManaged: boolean;
  providerResetSeq: number;
  /** Image_URL 输入缓冲；undefined=未编辑，显示已存值 */
  probeUrlDraft: string | undefined;
  onProbeUrlChange: (value: string) => void;
  onProbeUrlSave: () => void;
  addParamFormOpen: boolean;
  onAddParamFormOpen: () => void;
  onAddParamFormClose: () => void;
  paramOptionsModalOpen: boolean;
  onParamOptionsOpen: () => void;
  onParamOptionsClose: () => void;
  onDiscard: () => void;
  onAddModel: () => void;
  onAddProvider: () => void;
  onClearApiKey: () => void;
  onDeleteModel: () => void;
  onDeleteProvider: () => void;
}

export const ModelTab: React.FC<Props> = ({
  s,
  probe,
  envManaged,
  providerResetSeq,
  probeUrlDraft,
  onProbeUrlChange,
  onProbeUrlSave,
  addParamFormOpen,
  onAddParamFormOpen,
  onAddParamFormClose,
  paramOptionsModalOpen,
  onParamOptionsOpen,
  onParamOptionsClose,
  onDiscard,
  onAddModel,
  onAddProvider,
  onClearApiKey,
  onDeleteModel,
  onDeleteProvider,
}) => {
  const { state } = s;
  const m = state.model;
  const hasManagementOptions = Object.keys(m.paramOptions).length > 0;
  const hasProviderDraft = Object.keys(m.providerDraft).length > 0;
  const probeUrlStored = probeImageUrlOf(state.values);
  // 实测取值单源 = providers[].models[].media（取证即落库，页面不持临时结果）
  const selectedEntry = m.providers
    .find((p) => p.name === m.selectedProvider)
    ?.models.find((x) => x.name === m.selectedModel);
  const media = selectedEntry?.media;
  const isGenerationModel =
    m.outputModalities.includes('image') ||
    m.outputModalities.includes('video');
  // chat 腿只在「声明了图片输入」时才有意义；重叠型模型两行各管各腿，不可一并置灰
  const chatLegMuted =
    isGenerationModel && !m.inputModalities.includes('image');

  return (
    <div>
      <ModelTabSelector
        providers={m.providers}
        selectedProvider={m.selectedProvider}
        selectedModel={m.selectedModel}
        onSelectProvider={(name) => void s.selectProvider(name)}
        onSelectModel={(name) => void s.selectModel(name)}
        onAddModel={onAddModel}
        onAddProvider={onAddProvider}
      />
      <ModelTabParamsHeader
        saving={s.saving}
        envManaged={envManaged}
        hasManagementOptions={hasManagementOptions}
        hasProviderDraft={hasProviderDraft}
        isDirty={m.isDirty}
        onAddParam={onAddParamFormOpen}
        onManageOptions={onParamOptionsOpen}
        onDiscard={onDiscard}
      />
      <ModelTabParams
        params={m.params}
        baseline={m.baseline}
        ranges={m.ranges}
        options={m.paramOptions}
        envOverride={m.envOverride}
        disabled={s.saving}
        addFormOpen={addParamFormOpen}
        onAdd={s.addParam}
        onCancelAdd={onAddParamFormClose}
        onChange={s.setParam}
        onDelete={s.removeParam}
      />
      <ModelTabInputModalities
        value={m.inputModalities}
        baseline={m.inputModalitiesBaseline}
        envManaged={envManaged}
        onChange={s.setInputModalities}
      />
      <ImageUrlRow
        value={probeUrlDraft ?? probeUrlStored}
        onChange={onProbeUrlChange}
        onSave={onProbeUrlSave}
      />
      <ModelTabMediaProbe
        media={media}
        lastProbe={selectedEntry?.last_probe?.media}
        chatLegMuted={chatLegMuted}
        imageChecked={m.inputModalities.includes('image')}
        saving={s.saving}
        probing={probe.probing}
        genProbing={probe.genProbing}
        onProbe={() => void probe.runMediaProbe()}
      />
      <ModelTabOutputModalities value={m.outputModalities} />
      {isGenerationModel && (
        <ModelTabGenProbe
          media={media}
          lastProbe={selectedEntry?.last_probe?.output}
          outputModalities={m.outputModalities}
          saving={s.saving}
          probing={probe.probing}
          genProbing={probe.genProbing}
          onProbe={() => void probe.runGenProbe()}
        />
      )}
      <ModelTabProviderConfig
        name={m.selectedProvider}
        config={m.providerConfig[m.selectedProvider]}
        resetSeq={providerResetSeq}
        onSave={async (patch) => {
          // 自带按钮与底部保存栏同走 saveProviderDraft；失败 rethrow 保留输入
          const r = await s.saveProviderDraft(patch);
          if (!r.ok) throw new Error('provider-config-save-failed');
        }}
        onDraftChange={s.setProviderDraft}
      />
      <SectionTitle title="── ④ 操作区 ──" />
      <ModelActions
        configured={
          m.providerConfig[m.selectedProvider]?.api_key?.configured ?? false
        }
        envManaged={envManaged}
        onClearApiKey={onClearApiKey}
        onDeleteModel={onDeleteModel}
        onDeleteProvider={onDeleteProvider}
      />
      {/* 管理选项弹窗：保存后 refreshModels 重拉 param_options + baseline */}
      <ParamOptionsModal
        open={paramOptionsModalOpen}
        provider={m.selectedProvider}
        model={m.selectedModel}
        paramOptions={m.paramOptions}
        baseline={m.baseline}
        onClose={onParamOptionsClose}
        disabled={s.saving}
        onSaved={async () => {
          if (m.selectedProvider && m.selectedModel)
            await s.refreshModels({
              provider: m.selectedProvider,
              model: m.selectedModel,
            });
        }}
      />
    </div>
  );
};
