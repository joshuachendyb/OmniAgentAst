// 编辑历史: 2026-11-09 小欧 - 新建：模型 Tab 版式编排（①选择器/②参数区/③配置/④操作区 + 三个弹窗），逻辑全部下沉到面板 — 小欧-2026-11-09
// 2026-11-11 小欧 - Image_URL 行(ImageUrlRow)移除: 三个验证素材地址(probe_image_url/video/audio)统一回媒体页「外链图片」小节
//   直接编辑(SettingRow text 渲染, 走组保存), 模型 Tab 只留验证按钮行; 相关 props(probeUrlDraft/onProbeUrlChange/onProbeUrlSave)
//   与 probeUrlStored/probeImageUrlOf 一并移除 — 小欧-2026-11-11
// 2026-11-11 小欧 - 增 ModelTabRefCapability 附件引用能力矩阵面板(ref_capability_map 只读投影) — 小欧-2026-11-11
import React from 'react';
import { SectionTitle } from './SectionTitle';
import { ModelActions } from './ModelActions';
import { ParamOptionsModal } from './ParamOptionsModal';
import { ModelTabSelector } from './ModelTabSelector';
import { ModelTabParamsHeader } from './ModelTabParamsHeader';
import { ModelTabParams } from './ModelTabParams';
import { ModelTabInputModalities } from './ModelTabInputModalities';
// 2026-11-11 小欧 - 输入能力验证行统一组件（图片/视频/音频合并, 替换原 MediaProbe/ModalityProbe 两组件）— 小欧-2026-11-11
import { ModelTabInputProbe } from './ModelTabInputProbe';
import { ModelTabOutputModalities } from './ModelTabOutputModalities';
import { ModelTabRefCapability } from './ModelTabRefCapability';
import { ModelTabGenProbe } from './ModelTabGenProbe';
import { ModelTabProviderConfig } from './ModelTabProviderConfig';
import type { CapabilityProbe } from '../hooks/useCapabilityProbe';
import type { UseSettings } from '../hooks/useSettings';

interface Props {
  s: UseSettings;
  probe: CapabilityProbe;
  envManaged: boolean;
  providerResetSeq: number;
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
      <ModelTabInputProbe
        kind="image"
        media={media}
        lastProbe={selectedEntry?.last_probe?.media}
        checked={m.inputModalities.includes('image')}
        chatLegMuted={chatLegMuted}
        saving={s.saving}
        probing={probe.probing}
        genProbing={probe.genProbing}
        onProbe={() => void probe.runMediaProbe('image')}
      />
      {/* 视频/音频输入能力验证行: 只在声明对应输入模态时渲染(与图片行同口径) */}
      {m.inputModalities.includes('video') && (
        <ModelTabInputProbe
          kind="video"
          media={media}
          lastProbe={selectedEntry?.last_probe?.media}
          checked
          saving={s.saving}
          probing={probe.videoProbing}
          genProbing={probe.genProbing}
          onProbe={() => void probe.runMediaProbe('video')}
        />
      )}
      {m.inputModalities.includes('audio') && (
        <ModelTabInputProbe
          kind="audio"
          media={media}
          lastProbe={selectedEntry?.last_probe?.media}
          checked
          saving={s.saving}
          probing={probe.audioProbing}
          genProbing={probe.genProbing}
          onProbe={() => void probe.runMediaProbe('audio')}
        />
      )}
      <ModelTabOutputModalities value={m.outputModalities} />
      {/* 2026-11-11 小欧 - 附件引用能力矩阵(ref_capability_map 只读投影) — 小欧-2026-11-11 */}
      <ModelTabRefCapability map={selectedEntry?.ref_capability_map} />
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
