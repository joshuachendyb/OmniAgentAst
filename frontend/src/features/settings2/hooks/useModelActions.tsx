// 编辑历史: 2026-11-09 小欧 - 新建：模型/Provider 增删与密钥清空自 SettingsPage 移出；成功才关窗、失败 rethrow 保留输入 — 小欧-2026-11-09
import { modelApi } from '@/services/api/model.api';
import { confirmDanger } from '@/theme/SettingsModal';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import {
  ErrorType,
  handleApiError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';
import type { UseSettings } from './useSettings';

export interface ModelActionsUi {
  /** 当前待删除目标：`provider:<name>` 或 `model:<provider>::<model>` */
  deleteTarget: string | null;
  closeAddModel: () => void;
  closeAddProvider: () => void;
  closeDelete: () => void;
}

export type AddModelPayload = {
  provider: string;
  model: string;
  label: string;
  model_params?: Record<string, unknown>;
  range?: Record<string, { min: number; max: number }>;
  input_modalities?: string[];
  output_modalities?: string[];
  param_options?: Record<string, string[]>;
};

export type AddProviderPayload = {
  name: string;
  label: string;
  api_base: string;
  api_key?: string;
  timeout?: number;
  max_retries?: number;
  models?: string[];
};

export const useModelActions = (s: UseSettings, ui: ModelActionsUi) => {
  const { state } = s;

  /** 落盘成功后同步 mtime + 刷新模型列表（Provider 配置保存/清空 key/模型库保存共用收口） */
  const afterModelSaved = async (mtime: number) => {
    s.syncMtime(mtime);
    await s.refreshModels();
  };

  const submitAddModel = async (d: AddModelPayload) => {
    try {
      const res = await modelApi.addModel({
        provider: d.provider,
        model: d.model,
        label: d.label,
        ...(d.model_params ? { model_params: d.model_params } : {}),
        ...(d.range ? { range: d.range } : {}),
        ...(d.input_modalities ? { input_modalities: d.input_modalities } : {}),
        ...(d.output_modalities
          ? { output_modalities: d.output_modalities }
          : {}),
        ...(d.param_options ? { param_options: d.param_options } : {}),
      });
      s.syncMtime(res.mtime);
      showSuccess('模型已添加');
      await s.refreshModels({ provider: d.provider, model: d.model });
      // 成功才关窗；失败 rethrow 让弹窗保留输入
      ui.closeAddModel();
    } catch (e) {
      handleApiError(e);
      throw e;
    }
  };

  const submitAddProvider = async (d: AddProviderPayload) => {
    try {
      const res = await modelApi.addProvider(d);
      s.syncMtime(res.mtime);
      // 添加后引导切换新 Provider 配置区
      showSuccess('Provider 已添加，请在选择器切换到新 Provider 配置');
      await s.refreshModels();
      ui.closeAddProvider();
    } catch (e) {
      handleApiError(e);
      throw e;
    }
  };

  const clearApiKey = () => {
    const provider = state.model.selectedProvider;
    confirmDanger({
      title: '确定清空 api_key？',
      content: (
        <div
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
        >
          清空后：
          <ul style={{ margin: `${Spacing.SM}px 0 0`, paddingLeft: 20 }}>
            <li>「{provider}」的密钥被抹除，不可撤销</li>
            <li>该 Provider 的全部模型将立即无法调用</li>
            <li>需重新填写 api_key 才能恢复使用</li>
          </ul>
        </div>
      ),
      okText: '确认清空',
      onOk: async () => {
        try {
          const r = await modelApi.updateProvider(provider, { clear: true });
          showSuccess('api_key 已清空');
          // 清空是 api_key 的第二个写入口，须同清草稿，否则接着保存会把刚清空的密钥写回；
          // 同时立即本地更新 providerConfig，不等 reloadProviderCache（否则期间回填旧掩码）
          s.patchModel({
            providerConfig: {
              ...state.model.providerConfig,
              [provider]: {
                ...state.model.providerConfig[provider],
                api_key: { configured: false, masked: '' },
              },
            },
            providerDraft: {},
          });
          await afterModelSaved(r.mtime);
        } catch (e) {
          handleApiError(e);
        }
      },
    });
  };

  const confirmDelete = async () => {
    // 删除成功后 load() 全量重建，不先保存会静默丢弃当前焦点模型的未存参数/能力/删除意图
    if (!(await s.ensureModelSaved())) return;
    const target = ui.deleteTarget ?? '';
    try {
      let res;
      if (target.startsWith('provider:')) {
        res = await modelApi.deleteProvider(target.slice('provider:'.length));
        if (res.switched_to)
          showMessage(
            ErrorType.INFO,
            `已切换回默认 Provider：${res.switched_to}`
          );
      } else {
        // 模型名可含 '/'，用 '::' 分隔；取首个 '::'，模型名含 '::' 时不被截断误删
        const rest = target.slice('model:'.length);
        const sepIndex = rest.indexOf('::');
        const p = sepIndex >= 0 ? rest.slice(0, sepIndex) : '';
        const m = sepIndex >= 0 ? rest.slice(sepIndex + 2) : rest;
        res = await modelApi.deleteModel(p, m);
        if (res.switched_to)
          showMessage(ErrorType.INFO, `已切换回默认模型：${res.switched_to}`);
      }
      s.syncMtime(res.mtime);
      // 删除后整体 load()：焦点/currentRef/参数区全部重载对齐后端，杜绝前端停在已删模型上
      await s.load();
      // 成功才关删除确认，失败保留弹窗看错因
      ui.closeDelete();
    } catch (e) {
      handleApiError(e);
    }
  };

  return {
    afterModelSaved,
    submitAddModel,
    submitAddProvider,
    clearApiKey,
    confirmDelete,
  };
};
