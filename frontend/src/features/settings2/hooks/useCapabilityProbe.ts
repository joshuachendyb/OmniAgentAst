// 编辑历史: 2026-11-09 小欧 - 新建：图片/生成两条实测腿的忙态与收尾自 SettingsPage 移出（骨架共用，仅请求与文案分叉）— 小欧-2026-11-09
// 2026-11-11 小欧 - 输入验证泛化三态: 图片/视频/音频各自独立忙态与按钮, 同一收尾链(settleProbe) — 小欧-2026-11-11
// 2026-11-11 小欧 - 注释勘误: 忙态注释"互斥禁用"→"互不相扰"(各模态独立 loading 不阻塞)，与实现一致 — 小欧-2026-11-11
import { useState } from 'react';
import { modelApi } from '@/services/api/model.api';
import { settingsApi } from '@/services/api/settings.api';
import { ErrorType, showMessage, showSuccess } from '@/services/error/handler';
import type { UseSettings } from './useSettings';

export type MediaKind = 'image' | 'video' | 'audio';

export interface CapabilityProbe {
  /** 图片输入验证忙态(行按钮 loading) */
  probing: boolean;
  videoProbing: boolean;
  audioProbing: boolean;
  genProbing: boolean;
  runMediaProbe: (kind?: MediaKind) => Promise<void>;
  runGenProbe: () => Promise<void>;
}

export const useCapabilityProbe = (s: UseSettings): CapabilityProbe => {
  const [probing, setProbing] = useState(false);
  // 各模态独立忙态：与生成腿互不相扰（各自独立 loading，互不阻塞）
  const [videoProbing, setVideoProbing] = useState(false);
  const [audioProbing, setAudioProbing] = useState(false);
  // 生成验证独立忙态：与输入模态互不相扰（各自独立 loading，互不阻塞）
  const [genProbing, setGenProbing] = useState(false);
  const { refreshModels, syncMtime, state } = s;

  // 探测写盘绕过保存链，页面 providers 缓存与 mtime 都已过期；回填后紧接着的保存不再被守卫拒
  const reloadProbeResult = async () => {
    await refreshModels();
    try {
      syncMtime(await settingsApi.getMtime());
    } catch {
      // mtime 回填失败只影响下一次保存的守卫比对，静默
    }
  };

  // 未取证(限流/鉴权/5xx/排队/超时)不当实测结果；但已落库的部分腿仍需回读上界面
  const settleProbe = async (r: {
    ok: boolean;
    conclusive: boolean;
    persisted: boolean;
    message: string;
  }) => {
    if (r.persisted) await reloadProbeResult();
    if (!r.conclusive) {
      showMessage(ErrorType.WARNING, r.message);
      return;
    }
    if (r.ok) showSuccess(r.message);
    else showMessage(ErrorType.WARNING, r.message);
  };

  const runProbeLeg = async (kind: 'media' | 'output', mediaKind: MediaKind = 'image') => {
    // 探测目标 = ①选中的 provider+模型（输入验证腿与生成验证腿同一目标）
    const provider = state.model.selectedProvider;
    const model = state.model.selectedModel;
    const busySet =
      kind === 'output' ? setGenProbing
      : mediaKind === 'video' ? setVideoProbing
      : mediaKind === 'audio' ? setAudioProbing
      : setProbing;
    const isBusy =
      kind === 'output' ? genProbing
      : mediaKind === 'video' ? videoProbing
      : mediaKind === 'audio' ? audioProbing
      : probing;
    if (!provider || !model || isBusy) return;
    busySet(true);
    try {
      await settleProbe(
        await (kind === 'media'
          ? modelApi.probeMedia(provider, model, mediaKind)
          : modelApi.probeOutput(provider, model))
      );
    } catch (e) {
      // 请求侧失败(超时/断连)时后端可能已按组落库：回读一次，界面不停在旧结论
      if (kind === 'output') await reloadProbeResult();
      const timedOut = (e as { code?: string }).code === 'ECONNABORTED';
      showMessage(
        ErrorType.WARNING,
        kind === 'media'
          ? '探测失败，请检查 Provider 配置的网络可达性'
          : timedOut
            ? '生成验证超时（厂商任务可能仍在排队），本行只显示已落库的腿'
            : '生成验证失败，请检查 Provider 配置的网络可达性'
      );
    } finally {
      busySet(false);
    }
  };

  return {
    probing,
    videoProbing,
    audioProbing,
    genProbing,
    runMediaProbe: (kind: MediaKind = 'image') => runProbeLeg('media', kind),
    runGenProbe: () => runProbeLeg('output'),
  };
};
