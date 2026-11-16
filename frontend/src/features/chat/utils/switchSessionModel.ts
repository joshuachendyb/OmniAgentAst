// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 会话级模型切换唯一实现(推荐条一键切换/ModelPicker 共用)。
//   乐观锁 409 回读、失败提示、本地 L2 同步收口一处, 杜绝两套切换逻辑漂移 — 小欧-2026-11-16

/**
 * switchSessionModel —— 写会话级模型覆盖(L2)并同步本地状态。
 *
 * 与 ModelPicker/推荐条共用的唯一实现: 成功→setSessionModelOverride + 版本号前进;
 * 409→回读会话版本与模型; 其他错误→提示并保留原状态。
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
  } = opts;
  try {
    const res = await sessionApi.updateSessionModel(sessionId, next, version);
    if (res.version) setSessionVersion(res.version);
    setSessionModelOverride(next);
    return true;
  } catch (err: unknown) {
    const e = err as { response?: { status: number } };
    if (e?.response?.status === 409) {
      showSessionConflict();
      try {
        const sd = await sessionApi.getSessionMessages(sessionId);
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
