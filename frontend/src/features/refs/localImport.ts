// 编辑历史: 2026-11-06 小欧 - 新建: 同机本地导入入口(仅同机显示) — 小欧-2026-11-06
/** 同机本地导入 —— 附件「进系统」第二通道（仅同机）。
 *  与 uploadAttachments 同一条入队路径（复用 enqueue），只换数据源：
 *  上传拿 File[]，本地导入拿路径 → 后端读盘。
 *  两通道同一 enqueue(契约一致); 前端只调 API + 入队, 不做安全判定(薄前端)。
 */
import { showMessage, ErrorType } from '@/services/error/handler';
import { attachmentApi } from '@/services/api/attachment.api';
import { composerRefStore, newRefId, refLimitText } from './store';

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
): Promise<boolean> {
  try {
    const rec = await attachmentApi.importLocal(sessionId, path);
    // 与 uploadAttachments 的 enqueue 同一条入队路径（DRY）
    // push 超 MAX_REFS 返回 false → 点名提示
    const pushed = composerRefStore.push({
      id: newRefId(),
      kind: 'attachment',
      label: rec.original_name,
      path: rec.path,
      mime: rec.mime,
      size: rec.size,
      attachment_id: rec.id,
      lineRange: null,
    });
    if (!pushed) {
      showMessage(ErrorType.WARNING, refLimitText());
      return false;
    }
    return true;
  } catch (e) {
    // 按错误码区分提示: 403 = 跨机被后端拦, 不是"重试能解决"
    const code = (e as { response?: { data?: { code?: string } } })?.response
      ?.data?.code;
    if (code === 'LOCAL_IMPORT_DISABLED') {
      showMessage(
        ErrorType.UNKNOWN,
        '本地导入仅限本机使用（当前为远程访问），请改用上传'
      );
    } else {
      showMessage(ErrorType.UNKNOWN, `「${path}」导入失败，请重试`);
    }
    return false;
  }
}
