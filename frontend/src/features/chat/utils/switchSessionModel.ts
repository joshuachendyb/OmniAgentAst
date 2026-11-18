// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 会话级模型切换唯一实现(推荐条一键切换/ModelPicker 共用)。
//   乐观锁 409 回读、失败提示、本地 L2 同步收口一处, 杜绝两套切换逻辑漂移 — 小欧-2026-11-16

// 2026-11-18 opencode 修正: 增 isCurrent 会话在途判据 —— 原 await 之后无条件回写
//   setSessionVersion/setSessionModelOverride, 请求在途时切会话会把旧会话的模型覆盖
//   写到新会话上 — opencode-2026-11-18

/**
 * switchSessionModel —— 写会话级模型覆盖(L2)并同步本地状态。
 *
 * 与 ModelPicker/推荐条共用的唯一实现: 成功→setSessionModelOverride + 版本号前进;
 * 409→回读会话版本与模型; 其他错误→提示并保留原状态。
 *
 * isCurrent(可选): 请求在途期间用户可能已切到别的会话, 此时**丢弃本地回写** ——
 *   否则会把旧会话的模型覆盖和版本号写到新会话的 UI 状态上, 下次保存即撞 409 或被覆盖。
 */
import { sessionApi } from '@/services/api/session.api';
import type { SessionModelOverride } from '@/types/chat';
import { showSaveError, showSessionConflict } from '@/utils/chatMessages';

export interface SwitchSessionModelOpts {
  sessionId: string;
  next: SessionModelOverride | null;
  version: number;
  setSessionVersion: (v: number) => void;
  setSessionModelOverride: (v: SessionModelOverride | null) => void;
  /** 会话仍是最新目标? 缺省视为恒真(无会话切换语义的调用方) */
  isCurrent?: () => boolean;
}

export async function switchSessionModel(
  opts: SwitchSessionModelOpts
): Promise<boolean> {
  const {
    sessionId,
    next,
    version,
    setSessionVersion,
    setSessionModelOverride,
    isCurrent,
  } = opts;
  const alive = isCurrent ?? (() => true);
  try {
    const res = await sessionApi.updateSessionModel(sessionId, next, version);
    if (!alive()) return false; // 会话已切走: 结果只对旧会话有效, 不回写新会话状态
    if (res.version) setSessionVersion(res.version);
    setSessionModelOverride(next);
    return true;
  } catch (err: unknown) {
    const e = err as { response?: { status: number } };
    if (e?.response?.status === 409) {
      showSessionConflict();
      try {
        const sd = await sessionApi.getSessionMessages(sessionId);
        if (!alive()) return false;
        if (sd.version) setSessionVersion(sd.version);
        if (sd.sessionModel !== undefined) {
          setSessionModelOverride(
            sd.sessionModel as SessionModelOverride | null
          );
        }
      } catch {
        // 回读失败保持当前状态(静默) — 小欧-2026-08-22
      }
    } else {
      showSaveError('切换模型失败，请重试');
    }
    return false;
  }
}
