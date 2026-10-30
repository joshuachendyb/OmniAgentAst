// 编辑历史: 2026-10-29 小欧 - 新建：前端唯一读盘点(自 quote.ts:34-36 与 refresh.ts:35 分叉收口) — 小欧-2026-10-29

// 编辑历史: 2026-10-29 小欧 - 修正: probeRef 改整份读(取 size/mtime/truncated/loaded_lines, 不切片);
//   precheckRefs 改返回三元组 {checked,invalid,updated}(走 stat 端点, 只查存在性/mtime, 不读正文) — 小欧-2026-10-29

// 编辑历史: 2026-10-30 小欧 - probeRef 加独立 60s 上限: 正文读端点放宽到 120s 后, 探引用(只取
//   size/mtime)跟着变慢毫无道理 —— 死路径上 chip 要空转 120s 才报失败; 自设 AbortController,
//   中止归为 reason='timeout' — 小欧-2026-10-30

/**
 * probe —— 前端对引用的唯一读盘点
 *
 * 为什么收口(DRY)：重构前有 3 处自读盘(quote.ts:34-36 有外部/根内分流、refresh.ts:35 没有、
 *   pages/Files:784-792 又一份)，"选哪个接口"的知识也是两份。本文件是唯一实现。
 *
 * 职责边界：
 * - probeRef(path)：轻量读(不带 offset)，取 size/mtime/truncated/loaded_lines；读失败仍允许入队
 *   (chip 标"未校验")。
 * - precheckRefs(refs)：发送前走 stat 轻端点(GET /files/stat, 真源 browse_service, 落点 5.2.13;
 *   前端入口 fileApi.statFile 见 F12), 只取存在性/mtime, 不读正文(R3: 消掉点引用+发送前
 *   两次全读的 IO); mtime 与点引用时本地比对, 变化条目进 updated → 调用方(precheckOrBlock)
 *   点名提示"内容已更新"——mtime 仅本地比对, 不进 wire(4.5)。
 * - 不切片、不裁决：行区间由后端按 lineRange 直接读(前端不再切片, sliceByLineRange 已删)；体积裁决归后端。
 */
import { fileApi } from '@/services/api/file.api';
import { isDriveAbsPath } from '@/utils/projectPath';

export interface ProbeResult {
  ok: boolean;
  size?: number;
  mtime?: string; // 内部字段: 仅两次预检间本地比对, 不上行(4.5)
  truncated?: boolean;
  loaded_lines?: number;
  reason?: 'missing' | 'unsupported' | 'timeout';
}

/** 探引用的独立上限: 只取 size/mtime, 不该跟着正文读放宽到 120s — 小欧 2026-10-30 */
const PROBE_TIMEOUT_MS = 60_000;

/** 探一条引用：整份读(不带 offset)取 size/mtime；失败给 reason 供 chip 标"未校验"。 */
export const probeRef = async (path: string): Promise<ProbeResult> => {
  // 2026-10-30 小欧 - 独立 60s 上限: 死路径/网络盘上不该让 chip 空转 120s 才报失败
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), PROBE_TIMEOUT_MS);
  try {
    const r = isDriveAbsPath(path)
      ? await fileApi.readExternalFile(path, { signal: ac.signal })
      : await fileApi.readFile(path, { signal: ac.signal });
    return {
      ok: true,
      size: r.size,
      mtime: r.mtime,
      truncated: r.truncated,
      loaded_lines: r.loaded_lines,
    };
  } catch (e) {
    // 2026-10-30 小欧: 按后端 read 端点失败码细分 reason(接口枚举 missing/unsupported/timeout,
    //   原实现一律 missing 粗化): 415(UNSUPPORTED_TYPE/UNDECODABLE)→unsupported; 超时→timeout;
    //   404/400/403/其余网络→missing。失败仍允许入队"未校验", reason 供 chip 文案分支。
    const status = (e as { response?: { status?: number } })?.response?.status;
    const code = (e as { code?: string })?.code;
    const msg = (e as { message?: string })?.message ?? '';
    if (status === 415) return { ok: false, reason: 'unsupported' };
    // ERR_CANCELED 只可能来自上面的 60s 上限(本函数不接外部 signal), 故归 timeout
    if (
      code === 'ERR_CANCELED' ||
      code === 'ECONNABORTED' ||
      msg.includes('timeout')
    )
      return { ok: false, reason: 'timeout' };
    return { ok: false, reason: 'missing' };
  } finally {
    clearTimeout(timer);
  }
};

/** 发送前预检(轻, R3)：走 stat 端点(存在性/mtime, 不读正文), O(1)/条;
 *  失败标 invalid(红底+点名)并阻断。mtime 与入队时(probeRef)比对, 变化条目进 updated,
 *  由调用方(precheckOrBlock)发送前点名提示"内容已更新"——mtime 仅请求链本地留存, 不进 wire。
 */
export const precheckRefs = async <T extends { path: string; mtime?: string }>(
  refs: T[]
): Promise<{ checked: T[]; invalid: T[]; updated: T[] }> => {
  const checked: T[] = [];
  const invalid: T[] = [];
  const updated: T[] = [];
  for (const r of refs) {
    const st = await fileApi.statFile(r.path); // GET /files/stat, 真源 browse_service
    if (!st.ok) {
      invalid.push(r);
      continue;
    }
    if (r.mtime && st.mtime && st.mtime !== r.mtime) {
      updated.push(r); // 本地比对命中: 内容已在盘面更新
    }
    checked.push({ ...r, size: st.size } as T);
  }
  return { checked, invalid, updated };
};
