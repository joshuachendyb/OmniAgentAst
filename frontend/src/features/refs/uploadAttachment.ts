// 编辑历史: 2026-11-06 小欧 - 新建: 附件入引用区唯一实现(上传/拖拽/粘贴/③产物共用) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧 - 三堂会审(DRY): 导出 enqueue 供 localImport 复用 —— 上传/本地导入
//   两通道同一条入队路径, 附件 ref 构造只此一份(原 localImport 内联重写一份) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧 - 三堂会审(DRY): 上限数值单一真源 MAX_IMAGE_MB/MAX_FILE_MB, 字节换算与
//   文案派生共用(原 tip/rejectReason 两处文案硬编码 10MB/20MB) — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - F-01 修复: 上传前容量预检(occupancy + 本批 > MAX_REFS 整批拒绝),
//   根除"落库成功却入不了队"的服务端孤儿附件记录 — 小欧-2026-11-07
// 编辑历史: 2026-11-10 小欧 - 新增 ATTACHMENT_RULES 规则文案常量(单一真源): 按钮 Tooltip 与抽屉帮助图标共用 — 小欧-2026-11-10
// 编辑历史: 2026-11-11 小欧 - 容量预检与规则文案改读 getMaxRefs()(上限单真源后端) — 小欧-2026-11-11
// 编辑历史: 2026-11-14 小欧 - 上限改读后端 capabilities.limits(max_image_bytes/max_file_bytes),
//   删前端硬编码 10MB/20MB(双真源); 规则文案补「音频」并改由后端上限派生 — 小欧-2026-11-14
/**
 * uploadAttachment —— 「把文件送进引用区」的唯一实现（附件域）
 *
 * 三个入口（按钮选择 / 拖拽 / 粘贴截图）与 ③「存为附件」全部走这里：
 *   - 前置闸门（单批 ≤10、图片 ≤10MB、其他 ≤20MB）只此一份；
 *   - 先选文件、选中后才建会话，取消选择不产生空会话；
 *   - 类型白名单只留在后端（前端再列一份必然漂移）。
 *   - 前端只做体验预检，安全校验全在后端（删掉预检仍应全绿）。
 */
import {
  attachmentApi,
  type AttachmentRecord,
} from '@/services/api/attachment.api';
import {
  showMessage,
  showSuccess,
  handleApiError,
  ErrorType,
} from '@/services/error/handler';
import {
  composerRefStore,
  newRefId,
  refLimitText,
  getMaxRefs,
  getAttachSizeBytes,
  getAttachSizeMB,
} from './store';
import { quoteFile } from './quote';

/** 单批选择上限（10 = 一次选择上限；入队总上限见后端 max_refs） */
export const MAX_BATCH = 10;

/**
 * 附件规则说明(单一真源): 按钮 Tooltip 与抽屉标题帮助图标共用。
 * 类型清单与白名单同口径(含音频); 大小上限取 store 分档上限(后端 capabilities 写入)。
 */
export function attachmentRules(): string {
  const mb = getAttachSizeMB();
  return (
    '支持图片、视频、音频、PDF / Word / Excel / PPT、文本与代码文件；' +
    `图片 ≤${mb.image}MB、其他 ≤${mb.other}MB，一次最多 ${MAX_BATCH} 个、共 ${getMaxRefs()} 项；` +
    '其余类型（如 zip/exe）会被拒绝。'
  );
}

export interface UploadOptions {
  /** 当前会话 ID；为空表示新会话（选中文件后才建会话） */
  sessionId?: string | null;
  /** 无会话时创建并回填，返回新 sessionId；失败返回 null */
  ensureSession?: () => Promise<string | null>;
}

export interface UploadResult {
  ok: number;
  failed: number;
}

/** 前置闸门：单批数量 + 单文件大小（类型白名单由后端裁决；上限取 store 分档口径） */
function rejectReason(files: File[]): string | null {
  if (files.length > MAX_BATCH) {
    return `一次最多选择 ${MAX_BATCH} 个文件`;
  }
  const mb = getAttachSizeMB();
  for (const f of files) {
    if (f.size > getAttachSizeBytes(f.type)) {
      return `「${f.name}」超过大小限制（图片 ${mb.image}MB / 其他 ${mb.other}MB）`;
    }
  }
  return null;
}

/** 落盘成功后入队一条 attachment 引用；超 MAX_REFS 返回 false。
 *  2026-11-06 小欧 三堂会审(DRY): 导出供 localImport 复用 —— 上传/本地导入两通道同一条入队路径。 — 小欧-2026-11-06 */
export function enqueue(rec: AttachmentRecord): boolean {
  return composerRefStore.push({
    id: newRefId(),
    kind: 'attachment',
    label: rec.original_name,
    path: rec.path,
    mime: rec.mime,
    size: rec.size,
    attachment_id: rec.id,
    lineRange: null,
  });
}

/**
 * 上传一批文件并入队。
 *
 * 串行上传（不 Promise.all）：并发 10 条 multipart 会把进度、失败归属、对话顺序全搅乱，
 * 而单文件 ≤20MB 的串行总耗时对用户可接受（KISS）。
 * 失败不抛：调用方（antd Upload / 拖拽 / 粘贴）不需要 try/catch，逐个错误就地提示。
 */
export async function uploadAttachments(
  files: File[],
  opts: UploadOptions = {}
): Promise<UploadResult> {
  const result: UploadResult = { ok: 0, failed: 0 };
  if (files.length === 0) return result;

  const bad = rejectReason(files);
  if (bad) {
    showMessage(ErrorType.WARNING, bad);
    result.failed = files.length;
    return result;
  }

  // 2026-11-07 小欧 - F-01 容量预检: 已入队 + 本批 > MAX_REFS → 整批拒绝, 不发请求。
  //   原实现先上传后入队, 入队失败时附件已落库 → 服务端孤儿记录(列表可见但无引用指向)。
  //   从严整批拒绝(不部分上传): 前端无法预知后端返回的 path(去重替换不占新配额的
  //   边缘场景被误拒), 该场景极罕见且用户删一条 chip 即可继续, KISS 优先。
  if (composerRefStore.occupancy() + files.length > getMaxRefs()) {
    showMessage(ErrorType.WARNING, refLimitText());
    result.failed = files.length;
    return result;
  }

  const sid = opts.sessionId || (await opts.ensureSession?.());
  if (!sid) {
    showMessage(ErrorType.UNKNOWN, '会话创建失败，附件未上传');
    result.failed = files.length;
    return result;
  }

  let overLimit = 0;
  for (const f of files) {
    try {
      const rec = await attachmentApi.upload(sid, f);
      if (enqueue(rec)) result.ok += 1;
      else overLimit += 1;
    } catch (e) {
      // 后端已按 code 给出具体原因（类型/大小），但用户此刻只需要知道"这个文件没进去"
      handleApiError(e, { message: `「${f.name}」上传失败，请重试` });
      result.failed += 1;
    }
  }
  if (overLimit > 0) showMessage(ErrorType.WARNING, refLimitText());
  result.failed += overLimit;
  return result;
}

/**
 * 从剪贴板 / 拖拽的 DataTransfer 取文件（S0 一次做完）。
 *
 * 粘贴截图时浏览器给的 File.name 为空串，直接上传会落成无名文件；
 * 这里补一个带时间戳的名字（扩展名取 mime 子类型），落盘与 chip 都可读。
 * 粘贴纯文本时 dt.files 为空 → 返回 [] → 调用方不 preventDefault，粘贴文字行为零变化。
 */
export function filesFromDataTransfer(dt: DataTransfer | null): File[] {
  if (!dt) return [];
  const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const out: File[] = [];
  let unnamed = 0;
  for (const f of Array.from(dt.files)) {
    if (f.name) {
      out.push(f);
      continue;
    }
    unnamed += 1;
    const sub = (f.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
    out.push(
      new File([f], `粘贴截图-${stamp}-${unnamed}.${sub}`, {
        type: f.type || 'image/png',
      })
    );
  }
  return out;
}

/**
 * ③「存为附件」（S0）——概览产出物行的动作实现。
 *
 * 两种后端结果都要落成**一条普通引用**，用户视角只有一个结果：「它进引用区了」。
 * referenced：文件已在会话工作区 → 走 quoteFile（复用它的大小/存在性探测与提示），不复制文件。
 * copied    ：文件在工作区外 → 后端已复制并登记，这里直接把返回记录入队。
 */
// 编辑历史: 2026-11-07 小欧 - F-01 补齐: 存为附件前容量预检(occupancy>=MAX_REFS 整项拒绝)。
//   copied 分支落库后 enqueue 失败→孤儿附件; 从严预检与 uploadAttachment 一致, 避免了这条孤儿链。
//   (referenced 分支复用工作区文件本不占新配额, 但从严策略下满额也拦, 补一条 chip 即可继续。) — 小欧-2026-11-07
export async function collectArtifact(
  sessionId: string,
  sourcePath: string,
  taskId?: string | null
): Promise<boolean> {
  // F-01 容量预检(copied 会新增一条引用): 满额先拦, 避免后端复制落库后 enqueue 失败 → 孤儿附件。
  if (composerRefStore.occupancy() >= getMaxRefs()) {
    showMessage(ErrorType.WARNING, refLimitText());
    return false;
  }
  try {
    const r = await attachmentApi.collect(sessionId, sourcePath, taskId);
    if (r.mode === 'referenced') {
      const q = await quoteFile(r.path, { label: r.label, size: r.size });
      if (!q.ok) {
        showMessage(
          ErrorType.WARNING,
          '该产物已在工作区，但引用失败，请稍后重试'
        );
        return false;
      }
      showSuccess(`已引用「${r.label}」到对话`);
      return true;
    }
    const pushed = enqueue(r.attachment);
    if (!pushed) {
      showMessage(ErrorType.WARNING, refLimitText());
      return false;
    }
    showSuccess(`已存为附件「${r.attachment.original_name}」`);
    return true;
  } catch (e) {
    handleApiError(e, { message: '存为附件失败：产物可能已被移动或删除' });
    return false;
  }
}
