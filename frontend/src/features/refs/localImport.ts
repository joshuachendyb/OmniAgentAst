// 编辑历史: 2026-11-06 小欧 - 新建: 同机本地导入入口(仅同机显示) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧: (DRY) 删内联 push 构造, 改调 uploadAttachment.enqueue(唯一入队实现);
//   原注释"复用 enqueue"与实际不符(实际自写一份构造) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧: (DRY/KISS) 错误码提取走 errorCodeOf(唯一实现), 不再手动三层解构;
//   并修正信封路径(原读 data.code, 信封为 data.error.code) — 小欧-2026-11-06
// 2026-11-07 小欧 - 导入前容量预检(occupancy>=MAX_REFS 整项拒绝), 与 uploadAttachment 同判据 —
//   根除"落库成功却入不了队"的服务端孤儿附件记录 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 返回值改 {ok, code}: LOCAL_READ_DENIED 不在此弹通用错误,
//   交调用方弹授权确认后重试(目录粒度授权) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 编辑历史: 2026-11-11 小欧 - 容量预检改读 getMaxRefs()(上限单真源后端) — 小欧-2026-11-11
/** 同机本地导入 —— 附件「进系统」第二通道（仅同机）。
 *  与 uploadAttachments 同一条入队路径（复用 enqueue），只换数据源：
 *  上传拿 File[]，本地导入拿路径 → 后端读盘。
 *  两通道同一 enqueue(契约一致); 前端只调 API + 入队, 不做安全判定(薄前端)。
 */
import { errorCodeOf, showMessage, ErrorType } from '@/services/error/handler';
import { attachmentApi } from '@/services/api/attachment.api';
import { composerRefStore, getMaxRefs, refLimitText } from './store';
// 2026-11-06 小欧 三堂会审(DRY): 复用唯一入队实现, 不再内联构造附件 ref — 小欧-2026-11-06
import { enqueue } from './uploadAttachment';

/** 导入结果：code 为空 = 成功；LOCAL_READ_DENIED = 目录未授权，调用方弹确认后重试 */
export interface ImportLocalResult {
  ok: boolean;
  code?: string;
}

export async function getLocalCapability(): Promise<boolean> {
  try {
    const res = await attachmentApi.localCapability();
    return res.local_import;
  } catch {
    return false; // 探测失败按跨机处理（安全默认）
  }
}

export async function importLocal(
  sessionId: string,
  path: string
): Promise<ImportLocalResult> {
  // 容量预检: 已满则不发请求(与 uploadAttachment 同判据从严)。
  //   否则落库后 enqueue 失败 → 服务端孤儿附件记录(列表可见但无引用指向)。
  if (composerRefStore.occupancy() >= getMaxRefs()) {
    showMessage(ErrorType.WARNING, refLimitText());
    return { ok: false };
  }
  try {
    const rec = await attachmentApi.importLocal(sessionId, path);
    // 与 uploadAttachments 同一条入队路径（复用 enqueue, DRY）
    // push 超 MAX_REFS 返回 false → 点名提示
    const pushed = enqueue(rec);
    if (!pushed) {
      showMessage(ErrorType.WARNING, refLimitText());
      return { ok: false };
    }
    return { ok: true };
  } catch (e) {
    // 按错误码区分提示: LOCAL_IMPORT_DISABLED = 跨机被后端拦, 不是"重试能解决"
    // 2026-11-06 小欧 三堂会审(DRY/KISS): 错误码提取走 errorCodeOf(唯一实现), 不再手动三层解构 — 小欧-2026-11-06
    const code = errorCodeOf(e);
    if (code === 'LOCAL_READ_DENIED') {
      return { ok: false, code }; // 授权确认与重试由调用方负责，此处不提示
    }
    if (code === 'LOCAL_IMPORT_DISABLED') {
      showMessage(
        ErrorType.UNKNOWN,
        '本地导入仅限本机使用（当前为远程访问），请改用上传'
      );
    } else {
      showMessage(ErrorType.UNKNOWN, `「${path}」导入失败，请重试`);
    }
    return { ok: false, code };
  }
}
